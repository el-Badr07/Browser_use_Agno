"""🏠 MCP Airbnb Agent - Search for Airbnb listings!

This example shows how to create an agent that uses MCP and Llama 4 to search for Airbnb listings.

1. Run: `pip install groq mcp agno` to install the dependencies
2. Export your GROQ_API_KEY
3. Run: `python cookbook/examples/agents/airbnb_mcp.py` to run the agent
"""

import asyncio
from textwrap import dedent

from agno.agent import Agent
from agno.models.groq import Groq
from agno.models.google.gemini import Gemini
from agno.tools.mcp import MCPTools
from agno.tools.thinking import ThinkingTools


# async def run_agent(message: str) -> None:
#     async with MCPTools(
#         "npx -y @openbnb/mcp-server-airbnb --ignore-robots-txt"
#     ) as mcp_tools:
#         agent = Agent(
#             model=Groq( api_key="api_key"),
#             tools=[ThinkingTools(), mcp_tools],
#             instructions=dedent("""\
#             ## General Instructions
#             - Always start by using the think tool to map out the steps needed to complete the task.
#             - After receiving tool results, use the think tool as a scratchpad to validate the results for correctness
#             - Before responding to the user, use the think tool to jot down final thoughts and ideas.
#             - Present final outputs in well-organized tables whenever possible.
#             - Always provide links to the listings in your response.
#             - Show your top 10 recommendations in a table and make a case for why each is the best choice.

#             ## Using the think tool
#             At every step, use the think tool as a scratchpad to:
#             - Restate the object in your own words to ensure full comprehension.
#             - List the  specific rules that apply to the current request
#             - Check if all required information is collected and is valid
#             - Verify that the planned action completes the task\
#             """),
#             add_datetime_to_instructions=True,
#             show_tool_calls=True,
#             markdown=True,
#         )
#         await agent.aprint_response(message, stream=True)


# if __name__ == "__main__":
#     task = dedent("""\
#     I'm traveling to San Francisco from April 20th - May 8th. Can you find me the best deals for a 1 bedroom apartment?
#     I'd like a dedicated workspace and close proximity to public transport.\
#     """)
#     asyncio.run(run_agent(task))





import asyncio
from pathlib import Path
from textwrap import dedent

from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools.mcp import MCPTools
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def create_filesystem_agent(session):
    """Create and configure a high-performance filesystem agent with Groq and MCP."""
    # Initialize the MCP toolkit
    mcp_tools = MCPTools(session=session)
    await mcp_tools.initialize()

    # Create an agent with the MCP toolkit and Groq's fast LLM
    return Agent(
        model=Groq(id="llama-3.3-70b-versatile", api_key="api_key"),
        tools=[mcp_tools],
        role="You are a high-performance filesystem assistant powered by Groq and MCP.",
        # instructions=dedent("""\
        #     You are a high-performance filesystem assistant powered by Groq and MCP.
        #     Your combination of Groq's fast inference and MCP's efficient context handling
        #     makes you exceptionally quick at exploring and analyzing files.

        #     - Navigate the filesystem with lightning speed to answer questions
        #     - Use the list_allowed_directories tool to find directories that you can access
        #     - Highlight the performance benefits of the Groq+MCP combination when relevant
        #     - Provide clear context about files you examine
        #     - Use headings to organize your responses
        #     - Be concise and focus on relevant information\
        # """),
        markdown=True,
        show_tool_calls=True,
    )
async def create_web_agent(session):
    """Create and configure a web agent with Groq and MCP."""
    # Initialize the MCP toolkit
    mcp_tools = MCPTools(session=session)
    await mcp_tools.initialize()

    # Create an agent with the MCP toolkit and Groq's fast LLM
    return Agent(
        model=Groq(id="llama-3.3-70b-versatile", api_key="api_key"),
        model=Gemini(api_key="api_key"),
        tools=[mcp_tools],
        role="Your task is to use your web browsing capabilities to find information and take actions on the web.",
        instructions=dedent("""\
            You are a web assistant powered by Groq and MCP.
            Your combination of Groq's fast inference and MCP's efficient context handling
            makes you exceptionally quick at exploring the web.
            


        """),
        markdown=True,
        show_tool_calls=True,
    )

async def run_agent(message: str) -> None:
    """Run the filesystem agent with the given message."""
    # Initialize the MCP server
    server_params1 = StdioServerParameters(
        command="npx",
        args=[
            "-y",
            "@modelcontextprotocol/server-filesystem",
            str(Path(__file__).parent.parent.parent.parent),
        ],
    )
    server_params = StdioServerParameters(
        command="npx",
        args=[
            "-y",
            "@playwright/mcp@latest",
        ],
    )

    # Create a client session to connect to the MCP server
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            agent = await create_web_agent(session)

            # Run the agent
            await agent.aprint_response(message, stream=True)


# Example usage
if __name__ == "__main__":
    # Basic example - exploring project license
    # asyncio.run(run_agent("What is the license for this project?"))

    # # Performance demonstration example
    # asyncio.run(
    #     run_agent(
    #         "Show me the README.md and explain how Groq with MCP enables fast file analysis"
    #     )
    # )
    asyncio.run(
        run_agent("Look for a personality test on the web and take it. Then, summarize the results of the test and provide a link to the test you took.")

        )







