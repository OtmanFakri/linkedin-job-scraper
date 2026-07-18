from browser_use import Agent, Browser, Controller
# ChatGoogle(model='gemini-3-flash-preview')
from browser_use import ChatGoogle,CH
# from browser_use import ChatAnthropic  # ChatAnthropic(model='claude-sonnet-4-6')
import asyncio
import json
import os

controller = Controller()
HISTORY_FILE = 'commented_posts.json'

# Function bach n-checkiw wach l-post dertih qbel
@controller.action(description='Check if a post URL was already commented on')
def check_if_commented(url: str):
    if not os.path.exists(HISTORY_FILE):
        return False
    with open(HISTORY_FILE, 'r') as f:
        history = json.load(f)
    return url in history

# Function bach n-sauvgardiw l-URL jdid
@controller.action(description='Save a post URL to history after commenting')
def save_to_history(url: str):
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
    
    if url not in history:
        history.append(url)
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f)
    return "URL saved to history."

async def main():
    browser = Browser.from_system_chrome()

    agent = Agent(
        task="""
1. Access tiktok.com and use the search bar.
2. Search for posts/reels using keywords: 'resume tips', 'job search 2026', or 'ATS resume'.
3. For the most relevant and recent posts, navigate to the comment section.
4. Generate and post a unique comment in English based on this core message:
   'Resume tailoring is a pain. I built CVrow.com to automate it! One click to adapt your CV to any job description. Fast, ATS-friendly, and professional. Check it out!'
5. CRITICAL: Slightly vary the wording of each comment so they aren't identical. For example, change the opening or the call-to-action.
6. Implement a 'human-like' delay of 20-30 seconds after posting each comment.
7. Limit the action to 3-5 comments per session to maintain account safety.
        """,
        # llm=ChatBrowserUse(),
        llm=ChatGoogle(
            model='gemini-2.5-flash'
            # model='gemini-3-flash-preview'
            ),
        
        # llm=ChatAnthropic(model='claude-sonnet-4-6'),
        browser=browser,
        controller=controller,
    )
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
