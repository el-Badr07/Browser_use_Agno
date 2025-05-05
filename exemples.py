import asyncio
import os

from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools.mcp import MCPTools

from mcp import StdioServerParameters

from textwrap import dedent


Groq_API_KEY ="api_key"

async def run_agent(message: str) -> None:
    """Run the Playwright agent with the given message."""
    print("Starting run_agent...") # Added print

    server_params = StdioServerParameters(
        command="npx",
        args=[ "-y","@playwright/mcp@latest"] ,env=os.environ ,
    )
    print("StdioServerParameters created.") # Added print

    try: # Added try/except
        print("Entering MCPTools context manager...") # Added print
        async with MCPTools(server_params=server_params,) as mcp_tools:
            print("MCPTools context manager entered.") # Added print
            agent = Agent(
                model=Groq(api_key=Groq_API_KEY),
                tools=[mcp_tools],
                # Updated role:
                # role="You are a web browsing assistant. Use the provided browser tool to answer user requests.",
                instructions=dedent("""You are a web browsing assistant. Use the provided browser tool to answer user requests. \
                                        "function browser_close from MCPToolkit
                        function browser_wait from MCPToolkit
                        function browser_resize from MCPToolkit
                        function browser_console_messages from MCPToolkit
                        function browser_handle_dialog from MCPToolkit
                        function browser_file_upload from MCPToolkit
                        function browser_install from MCPToolkit
                        function browser_press_key from MCPToolkit
                        function browser_navigate from MCPToolkit
                        function browser_navigate_back from MCPToolkit
                        function browser_navigate_forward from MCPToolkit
                        function browser_network_requests from MCPToolkit
                        function browser_pdf_save from MCPToolkit
                        function browser_snapshot from MCPToolkit
                        function browser_click from MCPToolkit
                        function browser_drag from MCPToolkit
                        function browser_hover from MCPToolkit
                        function browser_type from MCPToolkit
                        function browser_select_option from MCPToolkit
                        function browser_take_screenshot from MCPToolkit
                        function browser_tab_list from MCPToolkit
                        function browser_tab_new from MCPToolkit
                        function browser_tab_select from MCPToolkit
                        function browser_tab_close from MCPToolkit"""),
                markdown=True,
                show_tool_calls=True,
                debug_mode=False,
            )
            print("Agent created.") # Added print

            print("Calling agent.aprint_response...") # Added print
            await agent.aprint_response(message=message, stream=True)
            print("agent.aprint_response finished.") # Added print

    except Exception as e:
        print(f"An error occurred: {e}") # Added error logging


if __name__ == "__main__":
    print("Script started.") # Added print
    asyncio.run(
        run_agent(
            "browse the web and find the best deals for a 1 bedroom apartment in San Francisco from April 20th to May 8th. ",
        )
    )
    print("Script finished.") # Added print
