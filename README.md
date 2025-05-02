# Agno Framework

## Introduction

The Agno framework is a powerful tool for building intelligent agents. It provides a flexible and extensible architecture for integrating various tools and models to create sophisticated agents capable of performing complex tasks.

## Features

- **Modular Design**: Easily integrate new tools and models.
- **Extensible**: Add custom tools and models to extend the framework's capabilities.
- **Asynchronous**: Built with asyncio for high performance and scalability.

## Installation

To install the Agno framework, use the following command:

```bash
pip install agno
```

## Usage

### Basic Example

Here's a basic example of how to create an agent using the Agno framework:

```python
import asyncio
from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools.mcp import MCPTools

async def main():
    agent = Agent(
        model=Groq(api_key="your_groq_api_key"),
        tools=[MCPTools()],
        role="You are an intelligent assistant.",
    )
    response = await agent.aprint_response("Hello, how can I assist you today?")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

### Adding Browser Use as a Tool

The Agno framework now supports the addition of browser use as a tool. This allows agents to interact with web pages, perform searches, and extract information from the web.

#### Example

Here's an example of how to use the browser tool in the Agno framework:

```python
import asyncio
from agno.agent import Agent
from agno.tools.browser import BrowserTool
from agno.models.groq import Groq

async def main():
    browser_tool = BrowserTool(headless=False)
    agent = Agent(
        model=Groq(api_key="your_groq_api_key"),
        tools=[browser_tool],
        role="You are a web browsing assistant.",
    )
    response = await agent.aprint_response("Search for the latest news on AI.")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

In this example, the `BrowserTool` is added to the agent's tools, allowing it to perform web browsing tasks. The agent is instructed to search for the latest news on AI, and the response is printed to the console.

## Contributing

Contributions are welcome! Please read the [contributing guidelines](CONTRIBUTING.md) before submitting a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
