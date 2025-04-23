import asyncio
from os import getenv

from agno.agent import Agent
from agno.tools.browser import BrowserTool # Use the updated tool from agno
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
    # Instantiate the browser toolkit
    browser_toolkit = BrowserTool(headless=False)

    try:
        agent = Agent(
            model=Groq(id="deepseek-r1-distill-llama-70b", api_key=Groq_API_KEY, temperature=0.0),
            tools=[browser_toolkit],
            # --- Restore Detailed Role ---
            role="""
            <instructions>
            - You are a meticulous web automation assistant.
            - Your goal is to fulfill the user's request by interacting with web pages using the provided browser tools.
            - Break down the user's request into smaller, sequential steps.
            - **VERY IMPORTANT: Perform ONLY ONE browser action (tool call) per response turn.**
            - For each step, decide which single browser tool is appropriate.
            - **Crucially**: Before interacting with elements (clicking, typing), you MUST use 'get_current_state' in a *previous* turn to understand the page structure (URL, title, interactive elements with indices) and plan your *next single* action.
            - Use 'get_text' or 'get_html' (as a single action) to extract information needed to answer the user or decide the next step.
            - After performing an action (navigate, click, input_text, scroll, etc.), the tool will return the *new* state of the browser. Analyze this new state in your *next* turn before deciding the *next single* action.
            - Think step-by-step about how to achieve the user's goal using the available tools, one step at a time.
            </instructions>

            <available_tools>
            - navigate(url: str): Go to a URL. Returns the new browser state.
            - get_current_state(): Get page URL, title, tabs, interactive element list with indices, and scroll position. Returns the current browser state as JSON.
            - find_element_by_attribute(attribute: str, value: str): Returns highlight index of first element with attribute=value, or '-1'.
            - click_element(index: int): Click an interactive element (link, button) by its index from get_current_state. Returns the new browser state.
            - input_text(index: int, text: str): Type text into an input element by its index from get_current_state. Returns the new browser state.
            - get_html(): Get the full HTML of the current page (may be truncated). Returns HTML string.
            - get_text(): Get the visible text content of the current page. Returns text string.
            - scroll_page(direction: str, amount_pixels: Optional[int]): Scroll ('up', 'down', 'top', 'bottom'). Returns the new browser state.
            - switch_tab(tab_id: int): Switch to a tab by ID from get_current_state. Returns the new browser state.
            - new_tab(url: Optional[str]): Open a new tab. Returns the new browser state.
            - close_tab(): Close the current tab. Returns the new browser state (or confirmation if last tab).
            - refresh_page(): Refresh the current page. Returns the new browser state.
            - take_screenshot(full_page: bool = True): Capture a screenshot. Returns confirmation message.
            - go_back(): Navigate back in history. Returns the new browser state.
            - go_forward(): Navigate forward in history. Returns the new browser state.
            </available_tools>

            <workflow_example>
            1. **Turn 1:** User asks to search for 'X' on a site.
            2. **Turn 1 Response:** Call `navigate` to go to the site's URL.
            3. **Turn 2:** Analyze the state returned by `navigate`.
            4. **Turn 2 Response:** Call `get_current_state` to confirm page load and find the search input index and search button index.
            5. **Turn 3:** Analyze the state returned by `get_current_state`. Identify indices.
            6. **Turn 3 Response:** Call `input_text` with the search input's index and 'X'.
            7. **Turn 4:** Analyze the state returned by `input_text`.
            8. **Turn 4 Response:** Call `click_element` with the search button's index.
            9. **Turn 5:** Analyze the state returned by `click_element` (search results page).
            10. **Turn 5 Response:** Call `get_text` or `get_html` to see the search results.
            11. **Turn 6:** Analyze the text/HTML. Extract the required information.
            12. **Turn 6 Response:** Provide the final answer to the user (no tool call).
            </workflow_example>

            <output_format>
            - Use markdown for your final response to the user.
            - When making a tool call, explain your reasoning for this single step based on the state from the *previous* turn.
            </output_format>
            """,
            # --- End Detailed Role ---
            markdown=True,
            show_tool_calls=True,
            debug_mode=True,
        )

        # --- Restore Original Task ---
        await agent.aprint_response("""
            1. Visit https://scholar.google.com/
            2. Search for "yann lecun" in the search bar.
            3. Click on the profile link for Yann LeCun.
            4. Extract the names of the first 5 papers listed on their profile.
            5. Extract the names of the first 5 co-authors listed.
            6. Summarize the information found on the profile (e.g., affiliation, research areas if available).
            """, stream=True)
        # --- End Original Task ---

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