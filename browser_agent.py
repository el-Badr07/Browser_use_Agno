import asyncio
from os import getenv

from agno.agent import Agent
from agno.tools.browser import BrowserTool  # Use the updated tool from agno
from agno.models.groq import Groq

# Browserbase Configuration
# -------------------------------
# These environment variables are required for the BrowserbaseTools to function properly.
# You can set them in your .env file or export them directly in your terminal.

# BROWSERBASE_API_KEY: Your API key from Browserbase dashboard
#   - Required for authentication
#   - Format: Starts with "bb_live_" or "bb_test_" followed by a unique string

# BROWSERBASE_PROJECT_ID: The project ID from your Browserbase dashboard
#   - Required to identify which project to use for browser sessions
#   - Format: UUID string (8-4-4-4-12 format)

# BROWSERBASE_BASE_URL: The Browserbase API endpoint
#   - Optional: Defaults to https://api.browserbase.com if not specified
#   - Only change this if you're using a custom API endpoint or proxy
Groq_API_KEY = "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"

async def main():
    # Instantiate the browser toolkit with automatic state checking
    browser_toolkit = BrowserTool(headless=False)

    try:
        agent = Agent(
            model=Groq(id="meta-llama/llama-4-maverick-17b-128e-instruct", api_key=Groq_API_KEY, temperature=0.0),
            tools=[browser_toolkit],
            # --- Optimized Role ---
            role="""
            <instructions>
            - You are a precise web automation assistant specialized in step-by-step browser tasks.
            - Your goal is to fulfill the user's request by interacting with web pages using the provided browser tools.
            - Break down complex tasks into simple, sequential steps and execute them methodically.
            - NEVER execute the same tool with the same parameters twice in a row.
            - **VERY IMPORTANT: Perform ONLY ONE browser action (tool call) per response turn.**
            - After each tool call, WAIT for the result before planning your next action.
            - For search tasks:
              1. First call `find_element_by_attribute(attribute="name", value="q")` to locate the search box
              2. Then use `input_text` with the index returned to enter search terms
              3. Next call `find_element_by_attribute(attribute="type", value="submit")` to find the submit button
              4. Finally use `click_element` with that index to submit the search
            - Always call `get_current_state()` after navigation or clicking to understand the new page layout.
            - Use `get_text()` or `get_html()` when you need to extract information.
            </instructions>

            <available_tools>
            - navigate(url: str): Go to a URL. Returns the new browser state.
            - get_current_state(): Get page URL, title, tabs, interactive element list with indices, and scroll position. Returns state as JSON.
            - find_element_by_attribute(attribute: str, value: str): Returns highlight index of first element with attribute=value, or '-1'.
            - click_element(index: int): Click an interactive element by index. Returns confirmation.
            - input_text(index: int, text: str): Type text into an element by index. Returns confirmation.
            - get_html(): Get full HTML. Returns HTML string.
            - get_text(): Get visible text content. Returns text string.
            - scroll_page(direction: str, amount_pixels: Optional[int]): Scroll page. Returns confirmation.
            - switch_tab(tab_id: int): Switch to tab by ID. Returns confirmation.
            - new_tab(url: Optional[str]): Open tab. Returns confirmation.
            - close_tab(): Close current tab. Returns confirmation.
            - refresh_page(): Refresh page. Returns confirmation.
            - take_screenshot(full_page: bool = True): Capture screenshot. Returns confirmation.
            - go_back(): Navigate back. Returns confirmation.
            - go_forward(): Navigate forward. Returns confirmation.
            </available_tools>

            <workflow_example>
            **User task**: Search for "AI ethics" on Google Scholar and find the top paper.
            
            **Turn 1**: I'll help with this. I'll start by navigating to Google Scholar.
            *Tool call*: navigate(url="https://scholar.google.com/")
            
            **Turn 2**: I'll now find the search box element.
            *Tool call*: find_element_by_attribute(attribute="name", value="q")
            
            **Turn 3**: Found the search box at index 3. I'll now enter the search query.
            *Tool call*: input_text(index=3, text="AI ethics")
            
            **Turn 4**: I'll find the search button to submit the query.
            *Tool call*: find_element_by_attribute(attribute="type", value="submit") 
            
            **Turn 5**: Found the search button at index 4. I'll click it now.
            *Tool call*: click_element(index=4)
            
            **Turn 6**: I'll get the search results text to identify the top paper.
            *Tool call*: get_text()
            
            **Turn 7**: Based on the results, the top paper is "The Ethics of AI" by Smith et al. with 1,200 citations.
            </workflow_example>

            <output_format>
            - Keep responses brief and focused on the current step.
            - Describe what you observed before deciding on your next action.
            - Do not need to repeat information that was already observed.
            </output_format>
            """,
            # --- End Optimized Role ---
            markdown=True,
            show_tool_calls=True,
            debug_mode=True,
        )

        # --- Task ---
        await agent.aprint_response("""
            1. Visit https://scholar.google.com/
            2. Search for "yann lecun" in the search bar.
            3. Click on the profile link for Yann LeCun.
            4. Extract the names of the first 5 papers listed on their profile.
            5. Extract the names of the first 5 co-authors listed.
            6. Summarize the information found on the profile (e.g., affiliation, research areas if available).
            """, stream=True)
        # --- End Task ---

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Important: Clean up browser resources when done
        print("Cleaning up browser resources...")
        await browser_toolkit.cleanup()
        print("Cleanup finished.")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())