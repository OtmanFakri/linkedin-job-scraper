from browser_use import Agent, Browser, Controller, ChatGoogle
from pydantic import BaseModel
import asyncio
import os
import csv
import json
from google.oauth2 import service_account
import sys
from telegram import send_job_post as tg_send

# Load Vertex AI service account credentials from config.json
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_FILE, "r", encoding="utf-8") as _f:
    _service_account_info = json.load(_f)

_credentials = service_account.Credentials.from_service_account_info(
    _service_account_info,
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
_project_id = _service_account_info["project_id"]
_location = "global"

controller = Controller()
CSV_FILE = "linkedin_jobs.csv"


class ReadShareToastParams(BaseModel):
    pass


TASK_TIMEOUT_SECONDS = 55 * 60  # 55 min max, so cron (hourly) never overlaps

@controller.action(
    description="After clicking 'Copy link to post', call this action to read the post URL directly from the confirmation toast that appears (it contains a 'View post' link with the real URL), then it automatically dismisses the toast.",
    param_model=ReadShareToastParams,
)
async def read_share_toast(params: ReadShareToastParams, browser):
    page = await browser.get_current_page()
    try:
        # Wait a moment for the toast to render
        await page.wait_for_selector("a:has-text('View post')", timeout=4000)
        url = await page.eval_on_selector("a:has-text('View post')", "el => el.href")

        # Close the toast so it doesn't block subsequent clicks
        close_btn = await page.query_selector(
            "button[aria-label='Dismiss'], button[aria-label='Close']"
        )
        if close_btn:
            await close_btn.click()

        if url:
            return url
        return "Toast appeared but no URL found in 'View post' link."
    except Exception as e:
        return f"Toast did not appear or link not found: {str(e)}"


# Define a controller action to save a job post to the CSV file
@controller.action(description="Save a single job post to the CSV file.")
def save_job_post(
    author: str, post_url: str, content: str, post_date: str, contact_info: str
):
    file_exists = os.path.exists(CSV_FILE)
    try:
        with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(
                    ["Author", "Post URL", "Content", "Post Date", "Contact Info"]
                )
            writer.writerow([author, post_url, content, post_date, contact_info])
        # Notify via Telegram immediately after saving
        tg_send(
            author=author,
            post_url=post_url,
            content=content,
            post_date=post_date,
            contact_info=contact_info,
        )
        return f"Successfully saved job post by {author} to {CSV_FILE}"
    except Exception as e:
        return f"Failed to save job post: {str(e)}"


async def main():
    # Read the user profile content from me.txt
    resume_path = "me.txt"
    if not os.path.exists(resume_path):
        print(f"Error: {resume_path} not found.")
        return

    with open(resume_path, "r", encoding="utf-8") as f:
        resume_content = f.read()

    # Use default system Chrome.
    # - cross_origin_iframes=False: prevents ax_tree "frame not found" errors
    #   caused by LinkedIn's many cross-origin iframes detaching mid-query.
    # - minimum_wait_page_load_time: gives the page more time to fully settle
    #   before browser-use tries to read the DOM.
    # - wait_between_actions: slows the agent down so LinkedIn doesn't throttle.
    browser = Browser.from_system_chrome(
        headless=False,
        cross_origin_iframes=False,
        minimum_wait_page_load_time=3.0,
        wait_between_actions=2.0,
    )

    agent = Agent(
        task=f"""
IMPORTANT CONSTRAINT: You must stay on the LinkedIn feed page (https://www.linkedin.com/feed/) for the entire task. 
- NEVER click the search bar, NEVER type any search query, NEVER navigate to a search results page.
- NEVER click on a job title, skill, or company name that might trigger a search or navigate away from the feed.
- The ONLY allowed actions on the feed are: scroll down, click the post's three-dot menu to copy its link, and call save_job_post.
- If you accidentally end up on a page other than the main feed, navigate back to https://www.linkedin.com/feed/ immediately and continue scrolling from where you were.
- Matching a post against the resume profile below is done by READING the post text only — it does NOT mean searching LinkedIn for those keywords.

1. Navigate to https://www.linkedin.com/
2. You should already be logged in. If the main feed is visible, proceed directly to step 3. If you unexpectedly see a login form, wait 10 seconds and check again — the user is likely already logged in via their browser profile.
3. Once on the LinkedIn feed, scroll down through the posts one section at a time.
4. For each post you see while scrolling, do the following:
   - Only extract from genuine feed posts written by a person (with an author name and post body). 
   - Skip sponsored/ad posts, 'People you may know' cards, and any content without a real author + timestamp.
   - Read the post's own text and compare it (mentally, do not search) against this profile to see if it mentions hiring, recruiting, or looking for candidates with skills matching this profile:
---
{resume_content}
---
5. If a post matches (mentions hiring for a role like full-stack developer, Spring Boot, React, Cypress, QA automation, or similar), extract the following fields:
    - Author (poster name)
    - URL of the post — copy it using these exact steps:
       a. Locate the three-dot menu icon ('...') at the top-right corner of the post.
       b. Click it to open the post options dropdown.
       c. Click "Copy link to post" from the dropdown menu.
       d. A confirmation toast will appear at the bottom-left with a "View post" link — call the `read_share_toast` action immediately to extract that URL and dismiss the toast. Use the returned value as post_url.
       e. If the toast does not appear within a few seconds, or the dropdown itself is not visible, try right-clicking the post timestamp (e.g., '1d ago') and copying that link instead.
   - Content (body text of the post)
   - Post Date (relative date like '1d ago', '3h ago')
   - Contact Info (any email, application link, or contact name; use 'N/A' if none found)
   - Call 'save_job_post' immediately with these fields.
6. Keep scrolling and repeating steps 4-5 until you have found and saved at least 15 matching posts, or until you've scrolled through at least 30 consecutive posts without finding any new matches.
7. Provide a summary of the posts you saved in your final answer.
""",
        llm=ChatGoogle(
            model="gemini-3.1-flash-lite",
            vertexai=True,
            credentials=_credentials,
            project=_project_id,
            location=_location,
        ),
        browser=browser,
        controller=controller,
        flash_mode=True,
        use_vision=False,
        max_steps=150,
    )

    try:
        await asyncio.wait_for(agent.run(), timeout=TASK_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        print("⚠️ Task exceeded time limit, forcing stop.")
    finally:
        try:
            await browser.close()
        except Exception as e:
            print(f"Error closing browser: {e}")

if __name__ == "__main__":
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as _csv:
        import csv as _csv_mod
        _csv_mod.writer(_csv).writerow(
            ["Author", "Post URL", "Content", "Post Date", "Contact Info"]
        )
    print(f"✅ Cleared {CSV_FILE} — starting fresh run.")
    
    asyncio.run(main())
    
    # Force-kill the process even if some background thread/connection is still holding the event loop
    sys.exit(0)