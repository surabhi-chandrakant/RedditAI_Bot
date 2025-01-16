import praw
import requests
import schedule
import time
import logging
from datetime import datetime
import pytz
from urllib3.exceptions import NameResolutionError
from logging.handlers import RotatingFileHandler
import os

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure rotating log handler
log_handler = RotatingFileHandler(
    "logs/reddit_bot.log",
    maxBytes=1024 * 1024,  # 1MB file size
    backupCount=5  # Keep 5 backup files
)
log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
log_handler.setFormatter(log_formatter)

logger = logging.getLogger('RedditBot')
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

# Add console handler for immediate feedback
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Reddit API credentials
    REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
    REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
    REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
    REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
    USER_AGENT = os.getenv("USER_AGENT")

    # Groq AI API credentials
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    # Subreddit configuration
    POST_SUBREDDIT = "test"
    COMMENT_SUBREDDIT = "learnmachinelearning"

    # Schedule configuration
    POST_SCHEDULE = "10:00"
    COMMENT_SCHEDULE = "12:00"


class RedditBot:
    def __init__(self):
        self.config = Config()
        self.reddit = None
        self.last_action_time = datetime.now()
        self.setup_reddit()

    def setup_reddit(self):
        """Initialize Reddit API connection"""
        try:
            self.reddit = praw.Reddit(
                client_id=self.config.REDDIT_CLIENT_ID,
                client_secret=self.config.REDDIT_CLIENT_SECRET,
                user_agent=self.config.USER_AGENT,
                username=self.config.REDDIT_USERNAME,
                password=self.config.REDDIT_PASSWORD
            )
            # Verify authentication
            username = self.reddit.user.me()
            logger.info(f"Reddit authentication successful - logged in as {username}")
            return True
        except Exception as e:
            logger.error(f"Reddit authentication failed: {e}")
            raise

    def generate_fallback_content(self, content_type="post", post_title=None):
        """Generate meaningful fallback content when AI is unavailable"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if content_type == "post":
            return f"""
# Today's AI and Technology Update

Hey Reddit community! 👋

Here's what's happening in the world of AI and technology:

1. The field of artificial intelligence continues to evolve rapidly
2. Machine learning applications are becoming more accessible
3. Data science remains a crucial skill in today's tech landscape

**Want to join the discussion?**
* What AI technologies are you most interested in?
* What challenges have you faced in learning about AI?
* What topics would you like to see covered in future posts?

---
*This is an automated post. Generated at: {current_time}*
            """
        else:  # comment fallback
            # Create context-aware comment based on post title
            if post_title:
                return self.generate_contextual_comment(post_title)
            return f"""
Thank you for sharing this interesting perspective! 

The intersection of technology and learning is fascinating, and discussions like these help us all grow and understand better.

Would love to hear more about your experiences and thoughts on this topic.

*Comment generated at: {current_time}*
            """

    def generate_contextual_comment(self, post_title):
        """Generate a context-aware comment based on post title"""
        title_lower = post_title.lower()
        
        # Dictionary of topic-based responses
        responses = {
            'learn': """
Great learning resource! Education in technology is crucial for staying current in our rapidly evolving field.

Some additional resources that might be helpful:
- Kaggle for hands-on practice
- Documentation for fundamental concepts
- Community forums for peer learning

Keep up the great work! What learning resources have you found most helpful?
            """,
            'help': """
Thanks for reaching out to the community! While I'm an automated response, the community here is very supportive.

Some general tips:
- Break down the problem into smaller parts
- Check the official documentation
- Use print statements for debugging
- Search for similar issues in the community

Hope this helps point you in the right direction!
            """,
            'project': """
Exciting project! Building practical applications is one of the best ways to learn and grow in this field.

Some suggestions for project development:
- Start with a clear scope
- Document your progress
- Test thoroughly
- Share updates with the community

Looking forward to seeing how your project develops!
            """
        }
        
        # Find the most relevant response based on post title
        for keyword, response in responses.items():
            if keyword in title_lower:
                return response
                
        # Default response if no keywords match
        return f"""
Thanks for sharing this interesting topic! 

These kinds of discussions are valuable for the community and help us all learn from each other's experiences.

Looking forward to seeing more perspectives in this thread.

*Generated at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
        """

    def generate_content(self, prompt, retries=3, delay=5):
        """Generate content using Groq AI with retry mechanism and fallback"""
        for attempt in range(retries):
            try:
                response = requests.post(
                    "https://api.groq.ai/generate",
                    json={"prompt": prompt, "max_tokens": 150},
                    headers={"Authorization": f"Bearer {self.config.GROQ_API_KEY}"}
                )
                response.raise_for_status()
                content = response.json().get("content", "")
                if content:
                    logger.info("Content generation successful")
                    return content
            except Exception as e:
                logger.warning(f"Content generation attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(delay)
        
        # If all attempts fail, use fallback content
        content_type = "post" if "post" in prompt.lower() else "comment"
        fallback = self.generate_fallback_content(content_type)
        logger.info("Using fallback content due to AI generation failure")
        return fallback

    def test_connection(self):
        """Test all connections and permissions"""
        try:
            # Test Reddit connection
            username = self.reddit.user.me()
            print(f"✓ Reddit connection successful (logged in as {username})")
            logger.info(f"Reddit connection test passed - user: {username}")

            # Test Groq AI connection
            test_content = self.generate_content("Write a short test message.")
            if test_content and len(test_content) > 0:
                print("✓ Groq AI connection successful")
                logger.info("Groq AI connection test passed")
            
            # Test posting permission
            test_post = self.reddit.subreddit(self.config.POST_SUBREDDIT).submit(
                title="Test Post - Will Delete",
                selftext="This is a test post to verify bot permissions."
            )
            print(f"✓ Posting test successful: {test_post.url}")
            logger.info(f"Post permission test passed - URL: {test_post.url}")
            
            # Delete test post
            test_post.delete()
            print("✓ Test post deleted successfully")
            
            return True

        except Exception as e:
            print(f"✕ Test failed: {str(e)}")
            logger.error(f"Connection test failed: {e}")
            return False

    def create_post(self):
        """Create a new Reddit post"""
        try:
            content = self.generate_content("Write an engaging Reddit post about machine learning or AI technology.")
            title = f"AI Insights & Discussion: {datetime.now().strftime('%Y-%m-%d')}"
            post = self.reddit.subreddit(self.config.POST_SUBREDDIT).submit(
                title=title, 
                selftext=content
            )
            logger.info(f"Successfully posted to r/{self.config.POST_SUBREDDIT}: {post.url}")
            print(f"✓ Created new post: {post.url}")
        except Exception as e:
            logger.error(f"Failed to create post: {e}")
            print(f"✕ Failed to create post: {e}")

    def create_comments(self):
        """Create comments on recent posts"""
        try:
            subreddit = self.reddit.subreddit(self.config.COMMENT_SUBREDDIT)
            for post in subreddit.new(limit=3):
                if not post.saved:
                    prompt = f"Write a helpful comment for this post title: {post.title}"
                    comment = self.generate_content(prompt)
                    # Pass post title to generate contextual fallback content
                    if "Unable to generate content" in comment:
                        comment = self.generate_fallback_content("comment", post.title)
                    reply = post.reply(comment)
                    post.save()
                    logger.info(f"Commented on post: {post.title}")
                    print(f"✓ Created new comment on: {post.title}")
                    time.sleep(5)  # Rate limiting
        except Exception as e:
            logger.error(f"Failed to create comments: {e}")
            print(f"✕ Failed to create comments: {e}")

    def run(self):
        """Main run loop with scheduling"""
        print("\nRunning initial tests...")
        if not self.test_connection():
            print("Initial tests failed. Please check the logs and your credentials.")
            return

        print("\nSetting up schedule...")
        schedule.every().day.at(self.config.POST_SCHEDULE).do(self.create_post)
        schedule.every().day.at(self.config.COMMENT_SCHEDULE).do(self.create_comments)
        
        print(f"\nBot is running with the following schedule:")
        print(f"- Posts: Daily at {self.config.POST_SCHEDULE}")
        print(f"- Comments: Daily at {self.config.COMMENT_SCHEDULE}")
        print("\nCreating initial post and comments for testing...")

        # Run once immediately for testing
        try:
            self.create_post()
            self.create_comments()
        except Exception as e:
            print(f"✕ Initial post/comment failed: {str(e)}")

        print("\nBot is now running in continuous mode. Press Ctrl+C to stop.")
        print("Check logs/reddit_bot.log for detailed logs.\n")

        # Main loop with better logging
        last_log_time = datetime.now()
        while True:
            try:
                schedule.run_pending()
                
                # Log status every 5 minutes
                current_time = datetime.now()
                if (current_time - last_log_time).seconds >= 300:
                    logger.info("Bot is running normally. Waiting for next scheduled task.")
                    print(".", end="", flush=True)  # Progress indicator
                    last_log_time = current_time
                
                time.sleep(60)
            except KeyboardInterrupt:
                print("\nBot stopped by user")
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(60)

if __name__ == "__main__":
    try:
        bot = RedditBot()
        bot.run()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
        logger.info("Bot stopped by user")
    except Exception as e:
        print(f"Critical error: {e}")
        logger.critical(f"Critical error: {e}")