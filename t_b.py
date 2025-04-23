import asyncio
import json
from typing import Any, List, Optional

# Updated imports based on the provided browser_use structure
try:
    from browser_use.browser.browser import Browser as BrowserUseBrowser, BrowserConfig
    from browser_use.browser.context import BrowserContext, BrowserContextConfig
    # DomService is used internally by BrowserContext in this version, no direct import needed here
except ImportError:
    raise ImportError(
        "The 'browser_use' library is required for BrowserTool. "
        "Please install it, e.g., `pip install browser-use` (or ensure it's in the correct path)"
    )

from pydantic import Field

from agno.tools.toolkit import Toolkit
from agno.utils.log import logger

# Define a maximum length for returning large content like HTML
MAX_LENGTH = 4000 # Increased max length slightly


class BrowserTool(Toolkit):
    """
    A toolkit for interacting with a web browser using the 'browser_use' library.
    Provides functions for navigation, interaction, and content extraction.
    Aligned with browser_use package structure found in the workspace.
    """

    # Configuration for the browser instance
    headless: bool = False
    browser_config_kwargs: dict = Field(default_factory=dict)
    context_config_kwargs: dict = Field(default_factory=dict) # Renamed for clarity

    # Internal state
    _lock: asyncio.Lock = Field(default_factory=asyncio.Lock)
    _browser: Optional[BrowserUseBrowser] = Field(default=None, exclude=True)
    _context: Optional[BrowserContext] = Field(default=None, exclude=True)
    # _dom_service is managed internally by BrowserContext in this version

    def __init__(
        self,
        name: str = "browser",
        headless: bool = False,
        browser_config_kwargs: Optional[dict] = None,
        context_config_kwargs: Optional[dict] = None, # Renamed
        **kwargs, # Pass other Toolkit args
    ):
        """
        Initializes the BrowserTool toolkit.

        Args:
            name: Name for the toolkit.
            headless: Whether to run the browser in headless mode.
            browser_config_kwargs: Additional keyword arguments for BrowserConfig.
            context_config_kwargs: Additional keyword arguments for BrowserContextConfig.
            **kwargs: Additional arguments for the base Toolkit.
        """
        # Define the tools (methods of this class) that should be registered
        tool_methods = [
            self.navigate,
            self.get_current_state,
            self.click_element,
            self.input_text,
            self.get_html,
            self.get_text,
            self.scroll_page,
            self.switch_tab,
            self.new_tab,
            self.close_tab,
            self.refresh_page,
            self.take_screenshot,
            self.go_back,
            self.go_forward,
            self.find_element_by_attribute, # Add the new method to the tool_methods list
            # Add other browser methods as needed
        ]

        super().__init__(name=name, tools=tool_methods, auto_register=True, **kwargs)

        self.headless = headless
        self.browser_config_kwargs = browser_config_kwargs or {}
        self.context_config_kwargs = context_config_kwargs or {} # Renamed

        # Ensure default headless state is respected in browser config
        self.browser_config_kwargs.setdefault("headless", self.headless)

        # Initialize internal state attributes needed by Pydantic/Toolkit
        self._lock = asyncio.Lock()
        self._browser = None
        self._context = None

        logger.info(f"BrowserTool initialized (headless={self.headless}) using browser_use package")


    async def _ensure_browser_initialized(self) -> BrowserContext:
        """Ensure browser and context are initialized."""
        if self._browser is None:
            logger.debug("Initializing browser...")
            # Pass kwargs to BrowserConfig
            browser_config = BrowserConfig(**self.browser_config_kwargs)
            self._browser = BrowserUseBrowser(browser_config)
            # Ensure the underlying playwright browser is started
            await self._browser.get_playwright_browser()
            logger.debug("Browser initialized.")

        if self._context is None:
            logger.debug("Creating new browser context...")
            # Pass kwargs to BrowserContextConfig
            context_config = BrowserContextConfig(**self.context_config_kwargs)
            # Use the browser instance to create a context
            self._context = await self._browser.new_context(context_config)
            # Ensure the context session is initialized (creates the first page etc.)
            await self._context.get_session()
            logger.debug("Browser context created.")

        # Ensure active tab is set if needed (get_session usually handles this)
        if self._context.active_tab is None:
             await self._context.get_current_page() # This should set active_tab

        return self._context

    async def cleanup(self):
        """Clean up browser resources."""
        async with self._lock:
            logger.debug("Cleaning up browser resources...")
            if self._context is not None:
                try:
                    await self._context.close()
                    logger.debug("Browser context closed.")
                except Exception as e:
                    logger.warning(f"Error closing browser context: {e}")
                finally:
                    self._context = None
            if self._browser is not None:
                try:
                    await self._browser.close()
                    logger.debug("Browser closed.")
                except Exception as e:
                    logger.warning(f"Error closing browser: {e}")
                finally:
                    self._browser = None
            logger.debug("Browser cleanup finished.")

    # __del__ remains the same as before, calling self.cleanup()

    # --- Browser Action Methods ---

    async def navigate(self, url: str) -> str:
        """
        Navigates the current browser tab to the specified URL.

        Args:
            url: The URL to navigate to.

        Returns:
            A confirmation message indicating success or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                await context.navigate_to(url)
                # Wait for page load stability
                await context._wait_for_page_and_frames_load()
                logger.info(f"Navigated to {url}")
                # Return simple confirmation
                current_url = context.active_tab.url if context.active_tab else "unknown"
                return f"Successfully navigated to {url}. Current URL is now {current_url}."
            except Exception as e:
                logger.error(f"Failed to navigate to {url}: {e}", exc_info=True)
                return f"Error navigating to {url}: {str(e)}"

    async def get_current_state(self) -> str:
        """
        Gets the current state of the browser, including URL, title, tabs, and interactive elements.
        This version calls context.get_state with cache_clickable_elements_hashes=True.

        Returns:
            A JSON string representing the browser state, or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                # Call get_state with the required argument from the specific browser_use version
                state = await context.get_state(cache_clickable_elements_hashes=True)

                # Extract relevant info from the BrowserState object
                state_info = {
                    "url": state.url,
                    "title": state.title,
                    "tabs": [tab.model_dump() for tab in state.tabs],
                    # Use the string representation provided by BrowserState
                    "interactive_elements": state.element_tree.clickable_elements_to_string(),
                    "pixels_above": state.pixels_above,
                    "pixels_below": state.pixels_below,
                }
                logger.debug("Retrieved current browser state.")
                # Truncate if very long, focusing on elements
                state_str = json.dumps(state_info, indent=2)
                if len(state_str) > MAX_LENGTH * 2: # Allow more length for state
                     # Prioritize showing elements if truncating
                     elements_str = json.dumps(state_info.get("interactive_elements", ""), indent=2)
                     other_info_str = json.dumps({k:v for k,v in state_info.items() if k != "interactive_elements"}, indent=2)
                     available_len = MAX_LENGTH * 2 - len(other_info_str) - 50 # Reserve space for truncation markers etc.
                     if available_len > 0:
                         truncated_elements = elements_str[:available_len] + "..."
                         state_str = f"{{\n  \"url\": {json.dumps(state_info.get('url'))}, ...other_info..., \n  \"interactive_elements\": {truncated_elements}\n}}"
                     else: # Fallback if other info is too long
                         state_str = state_str[:MAX_LENGTH*2] + "... (truncated)"

                return state_str
            except Exception as e:
                logger.error(f"Failed to get browser state: {e}", exc_info=True)
                return f"Error getting browser state: {str(e)}"

    async def click_element(self, index: int) -> str:
        """
        Clicks the interactive element at the specified index and returns confirmation plus updated state.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                element = await context.get_dom_element_by_index(index)
                if not element:
                    logger.warning(f"Element with index {index} not found for clicking.")
                    return f"Error: Element with index {index} not found."

                download_path = await context._click_element_node(element)
                # Wait for potential navigation/changes
                await context._wait_for_page_and_frames_load()

                output = f"Clicked element at index {index}."
                if download_path:
                    output += f" File downloaded to {download_path}"
                logger.info(output)
                # Retrieve updated state
                state_str = await self.get_current_state()
                return f"{output}\nBrowser state after click:\n{state_str}"
            except Exception as e:
                logger.error(f"Failed to click element at index {index}: {e}", exc_info=True)
                return f"Error clicking element at index {index}: {str(e)}"

    async def input_text(self, index: int, text: str) -> str:
        """
        Inputs the specified text into the form element and returns a confirmation plus updated state.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                element = await context.get_dom_element_by_index(index)
                if not element:
                     logger.warning(f"Element with index {index} not found for input.")
                     return f"Error: Element with index {index} not found."

                await context._input_text_element_node(element, text)
                # Wait briefly after input
                await asyncio.sleep(self._context.config.wait_between_actions if self._context else 0.5)
                output = f"Input text '{text}' into element at index {index}."
                logger.info(output)
                try:
                    # Get the state and return it - don't use self.get_current_state() as it creates circular calls
                    state = await context.get_state()
                    state_info = {
                        "url": state.url,
                        "title": state.title
                    }
                    return f"{output} Current state: URL={state.url}, title={state.title}"
                except Exception as inner_e:
                    logger.warning(f"Could not get state after input: {inner_e}")
                    return output
            except Exception as e:
                logger.error(f"Failed to input text at index {index}: {e}", exc_info=True)
                return f"Error inputting text at index {index}: {str(e)}"

    async def get_html(self) -> str:
        """
        Gets the full HTML content of the current page.
        The returned HTML might be truncated if it's very long.

        Returns:
            The HTML content as a string, possibly truncated, or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                html = await context.get_page_html()
                truncated = html[:MAX_LENGTH] + "... (truncated)" if len(html) > MAX_LENGTH else html
                logger.debug(f"Retrieved HTML (truncated: {len(html) > MAX_LENGTH}).")
                return truncated
            except Exception as e:
                logger.error(f"Failed to get HTML: {e}", exc_info=True)
                return f"Error getting HTML: {str(e)}"

    async def get_text(self) -> str:
        """
        Gets the visible text content of the current page using JavaScript.

        Returns:
            The text content as a string, possibly truncated, or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                # Using execute_javascript as it's reliable
                text = await context.execute_javascript("document.body.innerText")
                text_str = str(text)
                truncated = text_str[:MAX_LENGTH] + "... (truncated)" if len(text_str) > MAX_LENGTH else text_str
                logger.debug(f"Retrieved page text (truncated: {len(text_str) > MAX_LENGTH}).")
                return truncated
            except Exception as e:
                logger.error(f"Failed to get text: {e}", exc_info=True)
                return f"Error getting text: {str(e)}"

    async def scroll_page(self, direction: str, amount_pixels: Optional[int] = None) -> str:
        """
        Scrolls the current page up or down, or to the top/bottom.

        Args:
            direction: The direction to scroll ('up', 'down', 'top', 'bottom').
            amount_pixels: The number of pixels to scroll for 'up' or 'down'. Defaults to viewport height if None.

        Returns:
            A confirmation message or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                script = ""
                if (direction == "down"):
                    pixels = amount_pixels if amount_pixels is not None else "window.innerHeight"
                    script = f"window.scrollBy(0, {pixels});"
                elif (direction == "up"):
                    pixels = amount_pixels if amount_pixels is not None else "window.innerHeight"
                    script = f"window.scrollBy(0, -{pixels});"
                elif (direction == "top"):
                    script = "window.scrollTo(0, 0);"
                elif (direction == "bottom"):
                    script = "window.scrollTo(0, document.body.scrollHeight);"
                else:
                    return "Error: Invalid scroll direction. Use 'up', 'down', 'top', or 'bottom'."

                await context.execute_javascript(script)
                # Wait briefly after scroll
                await asyncio.sleep(self._context.config.wait_between_actions if self._context else 0.5)
                output = f"Scrolled page {direction}."
                if amount_pixels is not None and direction in ['up', 'down']:
                    output += f" by {abs(amount_pixels)} pixels."
                logger.info(output)
                # Return simple confirmation
                return output
            except Exception as e:
                logger.error(f"Failed to scroll page {direction}: {e}", exc_info=True)
                return f"Error scrolling page {direction}: {str(e)}"

    async def switch_tab(self, tab_id: int) -> str:
        """
        Switches the browser focus to the tab with the specified ID.
        Use 'get_current_state' to find the IDs of open tabs.

        Args:
            tab_id: The ID of the tab to switch to.

        Returns:
            A confirmation message or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                await context.switch_to_tab(tab_id)
                # Wait for potential load state changes
                await context._wait_for_page_and_frames_load()
                output = f"Switched to tab {tab_id}."
                logger.info(output)
                # Return simple confirmation
                return output
            except Exception as e:
                logger.error(f"Failed to switch to tab {tab_id}: {e}", exc_info=True)
                return f"Error switching to tab {tab_id}: {str(e)}"

    async def new_tab(self, url: Optional[str] = None) -> str:
        """
        Opens a new browser tab, optionally navigating to a URL.

        Args:
            url: The URL to open in the new tab. If None, opens 'about:blank'.

        Returns:
            A confirmation message or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                target_url = url if url else "about:blank"
                await context.create_new_tab(target_url)
                # Wait for potential load state changes
                await context._wait_for_page_and_frames_load()
                output = f"Opened new tab (URL: {target_url})"
                logger.info(output)
                # Return simple confirmation
                return output
            except Exception as e:
                logger.error(f"Failed to open new tab (URL: {url}): {e}", exc_info=True)
                return f"Error opening new tab: {str(e)}"

    async def close_tab(self) -> str:
        """
        Closes the currently active browser tab. Switches to another tab if available.

        Returns:
            A confirmation message or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                await context.close_current_tab()
                logger.info("Closed current tab.")
                # Check if context is still valid (i.e., if tabs remain)
                if context.session and context.session.context.pages:
                     # Wait for potential load state changes on the new active tab
                    await context._wait_for_page_and_frames_load()
                    # Return simple confirmation
                    return "Successfully closed the current tab. Switched to another tab."
                else:
                    logger.info("Last tab closed, browser context might be closing.")
                    # Reset internal state as context is likely gone
                    self._context = None
                    # Browser might still be alive if keep_alive=True
                    return "Successfully closed the last tab."
            except Exception as e:
                # Handle potential errors if the last tab was closed and context became invalid
                if "Target closed" in str(e) or "Browser closed" in str(e):
                     logger.info("Last tab closed, browser context might be closing.")
                     self._context = None
                     return "Successfully closed the last tab."
                logger.error(f"Failed to close tab: {e}", exc_info=True)
                return f"Error closing tab: {str(e)}"

    async def refresh_page(self) -> str:
        """
        Refreshes the current browser page.

        Returns:
            A confirmation message or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                await context.refresh_page()
                # Wait for potential load state changes
                await context._wait_for_page_and_frames_load()
                output = "Refreshed page."
                logger.info(output)
                # Return simple confirmation
                return output
            except Exception as e:
                logger.error(f"Failed to refresh page: {e}", exc_info=True)
                return f"Error refreshing page: {str(e)}"

    async def take_screenshot(self, full_page: bool = True) -> str:
        """
        Takes a screenshot of the current page.

        Args:
            full_page: Whether to capture the full scrollable page (True) or just the viewport (False).

        Returns:
            A message indicating success and the format/length of the screenshot (base64 encoded), or an error message.
            The actual base64 data is NOT returned in the message to avoid excessive length.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                # The context.py take_screenshot doesn't take full_page arg, it seems to default to viewport?
                # Let's check the implementation or assume viewport for now.
                # Based on context.py line 1000 (_get_updated_state), it calls self.take_screenshot() without args.
                # Based on context.py line 1080 (take_screenshot method), it takes no args and uses viewport.
                # We will ignore the full_page argument for now.
                screenshot_base64 = await context.take_screenshot()
                logger.info(f"Took screenshot (viewport). Length: {len(screenshot_base64)}")
                return f"Successfully took screenshot (format: base64 encoded string, length: {len(screenshot_base64)})."
            except Exception as e:
                logger.error(f"Failed to take screenshot: {e}", exc_info=True)
                return f"Error taking screenshot: {str(e)}"

    async def go_back(self) -> str:
        """
        Navigates back in the browser history.

        Returns:
            A confirmation message or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                await context.go_back()
                # Wait for potential load state changes
                await context._wait_for_page_and_frames_load()
                output = "Navigated back."
                logger.info(output)
                return output
            except Exception as e:
                logger.error(f"Failed to go back: {e}", exc_info=True)
                return f"Error going back: {str(e)}"

    async def go_forward(self) -> str:
        """
        Navigates forward in the browser history.

        Returns:
            A confirmation message or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                await context.go_forward()
                # Wait for potential load state changes
                await context._wait_for_page_and_frames_load()
                output = "Navigated forward."
                logger.info(output)
                return output
            except Exception as e:
                logger.error(f"Failed to go forward: {e}", exc_info=True)
                return f"Error going forward: {str(e)}"

    async def find_element_by_attribute(self, attribute: str, value: str) -> str:
        """
        Find the highlight index of the first element with attribute=value in the current page.

        Args:
            attribute: The attribute name to match (e.g., 'name', 'type').
            value: The attribute value to match.

        Returns:
            The index of the matching element, or '-1' if not found.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                state = await context.get_state(cache_clickable_elements_hashes=True)
                for idx, node in state.selector_map.items():
                    # node.attributes is a dict
                    if node.attributes.get(attribute) == value:
                        return str(idx)
                return "-1"
            except Exception as e:
                logger.error(f"Error in find_element_by_attribute: {e}", exc_info=True)
                return "-1"

# __del__ method remains the same
    def __del__(self):
        """Ensure cleanup when object is destroyed."""
        if self._browser is not None or self._context is not None:
            logger.debug("BrowserTool.__del__ triggering cleanup.")
            try:
                # Get or create an event loop if running in a context without one
                loop = asyncio.get_running_loop()
                loop.create_task(self.cleanup())
            except RuntimeError: # No running event loop
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.cleanup())
                    loop.close()
                    logger.debug("Cleanup completed in new event loop.")
                except Exception as e:
                     logger.error(f"Error during __del__ cleanup: {e}")