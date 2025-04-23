import asyncio
import json
from typing import Any, List, Optional

# Attempt to import browser_use, provide guidance if missing
try:
    from browser_use import Browser as BrowserUseBrowser
    from browser_use import BrowserConfig
    from browser_use.browser.context import BrowserContext, BrowserContextConfig
    from browser_use.dom.service import DomService
except ImportError:
    raise ImportError(
        "The 'browser_use' library is required for BrowserTool. "
        "Please install it, e.g., `pip install browser_use`"
    )

from pydantic import Field

from agno.tools.toolkit import Toolkit
from agno.utils.log import logger

# Define a maximum length for returning large content like HTML
MAX_LENGTH = 2000


class BrowserTool(Toolkit):
    """
    A toolkit for interacting with a web browser using the 'browser_use' library.
    Provides functions for navigation, interaction, and content extraction.
    """

    # Configuration for the browser instance
    headless: bool = False
    browser_config_kwargs: dict = Field(default_factory=dict)
    context_config: Optional[BrowserContextConfig] = None

    # Internal state
    _lock: asyncio.Lock = Field(default_factory=asyncio.Lock)
    _browser: Optional[BrowserUseBrowser] = Field(default=None, exclude=True)
    _context: Optional[BrowserContext] = Field(default=None, exclude=True)
    _dom_service: Optional[DomService] = Field(default=None, exclude=True)

    def __init__(
        self,
        name: str = "browser",
        headless: bool = False,
        browser_config_kwargs: Optional[dict] = None,
        context_config: Optional[BrowserContextConfig] = None,
        **kwargs, # Pass other Toolkit args
    ):
        """
        Initializes the BrowserTool toolkit.

        Args:
            name: Name for the toolkit.
            headless: Whether to run the browser in headless mode.
            browser_config_kwargs: Additional keyword arguments for BrowserConfig.
            context_config: Configuration for the browser context.
            **kwargs: Additional arguments for the base Toolkit.
        """
        # Define the tools (methods of this class) that should be registered
        # We let Toolkit's auto-register handle methods based on include/exclude rules passed in kwargs
        # If no include/exclude is passed, it registers all public methods not starting with _
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
            # Add other browser methods as needed
        ]

        super().__init__(name=name, tools=tool_methods, auto_register=True, **kwargs)

        self.headless = headless
        self.browser_config_kwargs = browser_config_kwargs or {}
        self.context_config = context_config or BrowserContextConfig()

        # Ensure default headless state is respected
        self.browser_config_kwargs.setdefault("headless", self.headless)

        # Initialize internal state attributes needed by Pydantic/Toolkit
        self._lock = asyncio.Lock()
        self._browser = None
        self._context = None
        self._dom_service = None

        logger.info(f"BrowserTool initialized (headless={self.headless})")


    async def _ensure_browser_initialized(self) -> BrowserContext:
        """Ensure browser and context are initialized."""
        if self._browser is None:
            logger.debug("Initializing browser...")
            self._browser = BrowserUseBrowser(BrowserConfig(**self.browser_config_kwargs))
            logger.debug("Browser initialized.")

        if self._context is None:
            logger.debug("Creating new browser context...")
            self._context = await self._browser.new_context(self.context_config)
            self._dom_service = DomService(await self._context.get_current_page())
            logger.debug("Browser context created.")

        # Ensure dom_service points to the current page if tabs changed etc.
        # This might need refinement based on how tab switching affects DomService
        current_page = await self._context.get_current_page()
        if self._dom_service is None or self._dom_service.page != current_page:
             self._dom_service = DomService(current_page)

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
                    self._dom_service = None
            if self._browser is not None:
                try:
                    await self._browser.close()
                    logger.debug("Browser closed.")
                except Exception as e:
                    logger.warning(f"Error closing browser: {e}")
                finally:
                    self._browser = None
            logger.debug("Browser cleanup finished.")

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
                # Update DOM service after navigation
                self._dom_service = DomService(await context.get_current_page())
                logger.info(f"Navigated to {url}")
                return f"Successfully navigated to {url}"
            except Exception as e:
                logger.error(f"Failed to navigate to {url}: {e}", exc_info=True)
                return f"Error navigating to {url}: {str(e)}"

    async def get_current_state(self) -> str:
        """
        Gets the current state of the browser, including URL, title, tabs, and interactive elements.

        Returns:
            A JSON string representing the browser state, or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                state = await context.get_state()
                # Ensure element tree is up-to-date for interactive elements
                await self._dom_service.get_element_tree()
                state_info = {
                    "url": state.url,
                    "title": state.title,
                    "tabs": [tab.model_dump() for tab in state.tabs],
                    "interactive_elements": state.element_tree.clickable_elements_to_string(),
                }
                logger.debug("Retrieved current browser state.")
                return json.dumps(state_info, indent=2)
            except Exception as e:
                logger.error(f"Failed to get browser state: {e}", exc_info=True)
                return f"Error getting browser state: {str(e)}"

    async def click_element(self, index: int) -> str:
        """
        Clicks the interactive element (like a button or link) at the specified index.
        Use 'get_current_state' to find the index of the element you want to click.

        Args:
            index: The 0-based index of the interactive element to click.

        Returns:
            A confirmation message indicating success, potential download path, or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                element = await context.get_dom_element_by_index(index)
                if not element:
                    logger.warning(f"Element with index {index} not found for clicking.")
                    return f"Error: Element with index {index} not found."

                download_path = await context._click_element_node(element)
                # Update DOM service after potential navigation/change
                self._dom_service = DomService(await context.get_current_page())

                output = f"Clicked element at index {index}."
                if download_path:
                    output += f" File downloaded to {download_path}"
                logger.info(output)
                return output
            except Exception as e:
                logger.error(f"Failed to click element at index {index}: {e}", exc_info=True)
                return f"Error clicking element at index {index}: {str(e)}"

    async def input_text(self, index: int, text: str) -> str:
        """
        Inputs the specified text into the form element (like an input field or textarea) at the given index.
        Use 'get_current_state' to find the index of the element you want to interact with.

        Args:
            index: The 0-based index of the form element.
            text: The text to input into the element.

        Returns:
            A confirmation message indicating success or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                element = await context.get_dom_element_by_index(index)
                if not element:
                     logger.warning(f"Element with index {index} not found for input.")
                     return f"Error: Element with index {index} not found."

                await context._input_text_element_node(element, text)
                # Update DOM service after potential change
                self._dom_service = DomService(await context.get_current_page())
                logger.info(f"Input text into element at index {index}.")
                return f"Successfully input text into element at index {index}."
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
                truncated = html[:MAX_LENGTH] + "..." if len(html) > MAX_LENGTH else html
                logger.debug(f"Retrieved HTML (truncated: {len(html) > MAX_LENGTH}).")
                return truncated
            except Exception as e:
                logger.error(f"Failed to get HTML: {e}", exc_info=True)
                return f"Error getting HTML: {str(e)}"

    async def get_text(self) -> str:
        """
        Gets the visible text content of the current page.

        Returns:
            The text content as a string, or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                # Using execute_javascript might be more reliable than a dedicated method if available
                text = await context.execute_javascript("document.body.innerText")
                logger.debug("Retrieved page text.")
                # Consider truncating text as well if it can be extremely long
                return str(text)[:MAX_LENGTH] + "..." if len(str(text)) > MAX_LENGTH else str(text)
            except Exception as e:
                logger.error(f"Failed to get text: {e}", exc_info=True)
                return f"Error getting text: {str(e)}"

    async def scroll_page(self, direction: str, amount_pixels: Optional[int] = None) -> str:
        """
        Scrolls the current page up or down.

        Args:
            direction: The direction to scroll ('up', 'down', 'top', 'bottom').
            amount_pixels: The number of pixels to scroll for 'up' or 'down'. Defaults to viewport height.

        Returns:
            A confirmation message indicating success or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                script = ""
                if direction == "down":
                    pixels = amount_pixels if amount_pixels is not None else "window.innerHeight"
                    script = f"window.scrollBy(0, {pixels});"
                elif direction == "up":
                    pixels = amount_pixels if amount_pixels is not None else "window.innerHeight"
                    script = f"window.scrollBy(0, -{pixels});"
                elif direction == "top":
                    script = "window.scrollTo(0, 0);"
                elif direction == "bottom":
                    script = "window.scrollTo(0, document.body.scrollHeight);"
                else:
                    return "Error: Invalid scroll direction. Use 'up', 'down', 'top', or 'bottom'."

                await context.execute_javascript(script)
                logger.info(f"Scrolled page {direction}.")
                return f"Successfully scrolled page {direction}."
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
            A confirmation message indicating success or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                await context.switch_to_tab(tab_id)
                # Update DOM service to the new active page
                self._dom_service = DomService(await context.get_current_page())
                logger.info(f"Switched to tab {tab_id}.")
                return f"Successfully switched to tab {tab_id}."
            except Exception as e:
                logger.error(f"Failed to switch to tab {tab_id}: {e}", exc_info=True)
                return f"Error switching to tab {tab_id}: {str(e)}"

    async def new_tab(self, url: Optional[str] = None) -> str:
        """
        Opens a new browser tab, optionally navigating to a URL.

        Args:
            url: The URL to open in the new tab. If None, opens a blank tab.

        Returns:
            A confirmation message indicating success or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                await context.create_new_tab(url)
                 # Update DOM service to the new active page
                self._dom_service = DomService(await context.get_current_page())
                msg = f"Opened new tab (URL: {url})" if url else "Opened new blank tab."
                logger.info(msg)
                return f"Successfully {msg}"
            except Exception as e:
                logger.error(f"Failed to open new tab (URL: {url}): {e}", exc_info=True)
                return f"Error opening new tab: {str(e)}"

    async def close_tab(self) -> str:
        """
        Closes the currently active browser tab.

        Returns:
            A confirmation message indicating success or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                await context.close_current_tab()
                 # Update DOM service to the new active page (if any tabs left)
                try:
                    self._dom_service = DomService(await context.get_current_page())
                except Exception: # Might fail if last tab was closed
                    self._dom_service = None
                    logger.info("Last tab closed.")
                logger.info("Closed current tab.")
                return "Successfully closed current tab."
            except Exception as e:
                logger.error(f"Failed to close tab: {e}", exc_info=True)
                return f"Error closing tab: {str(e)}"

    async def refresh_page(self) -> str:
        """
        Refreshes the current browser page.

        Returns:
            A confirmation message indicating success or an error message.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                await context.refresh_page()
                # Update DOM service after refresh
                self._dom_service = DomService(await context.get_current_page())
                logger.info("Refreshed page.")
                return "Successfully refreshed page."
            except Exception as e:
                logger.error(f"Failed to refresh page: {e}", exc_info=True)
                return f"Error refreshing page: {str(e)}"

    async def take_screenshot(self, full_page: bool = True) -> str:
        """
        Takes a screenshot of the current page.

        Args:
            full_page: Whether to capture the full scrollable page (True) or just the viewport (False).

        Returns:
            A message indicating success and the format of the screenshot (base64 encoded), or an error message.
            Note: The actual base64 data is not returned directly in the message to avoid excessive length.
                  A system message or alternative mechanism might be needed if the image data is required by the agent.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                screenshot_base64 = await context.take_screenshot(full_page=full_page)
                logger.info(f"Took screenshot (full_page={full_page}). Length: {len(screenshot_base64)}")
                # Avoid returning the full base64 string here.
                # If the agent needs the image, a different mechanism (like saving to file or a dedicated result type) is better.
                return f"Successfully took screenshot (format: base64 encoded string, length: {len(screenshot_base64)})."
                # Potential future enhancement: return a ToolResult object with output and system fields
                # return ToolResult(output="Screenshot captured.", system=screenshot_base64)
            except Exception as e:
                logger.error(f"Failed to take screenshot: {e}", exc_info=True)
                return f"Error taking screenshot: {str(e)}"

    # Add helper method to find element index by attribute
    async def find_element_by_attribute(self, attribute: str, value: str) -> str:
        """
        Find the highlight index of the first interactive element whose attribute equals value.

        Args:
            attribute: The name of the attribute to search (e.g., 'name', 'type', 'placeholder').
            value: The value to match.

        Returns:
            The index as a string, or '-1' if not found.
        """
        async with self._lock:
            try:
                context = await self._ensure_browser_initialized()
                # Update DOM service to ensure element_tree is current
                await self._dom_service.get_element_tree()
                state = await context.get_state(cache_clickable_elements_hashes=True)
                # selector_map: index -> DOMElementNode
                for idx, node in state.selector_map.items():
                    if node.attributes.get(attribute) == value:
                        return str(idx)
                return "-1"
            except Exception as e:
                logger.error(f"Error finding element by {attribute}={value}: {e}", exc_info=True)
                return "-1"
