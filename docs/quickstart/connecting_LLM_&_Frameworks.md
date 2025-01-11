Cillow can be used with any LLM or AI framework.

## Contents

- [LiteLLM](#litellm)
- [CrewAI](#crewai)
- [LlamaIndex](#llamaindex)
- [LangChain](#langchain)

## LiteLLM

Call all LLM APIs using the OpenAI format [Bedrock, Huggingface, VertexAI, TogetherAI, Azure, OpenAI, Groq etc.] through [LiteLLM](https://github.com/BerriAI/litellm)

```python
# pip install litellm cillow
import cillow
from litellm import completion

INSTRUCTION = "You are a helpful assistant that can execute python code in a Jupyter notebook. Only respond with the code to be executed and nothing else. Strip backticks in code blocks."

response = completion(
    model="groq/llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": INSTRUCTION},
        {"role": "user", "content": "Calculate how many 'r's are in the word 'strawberry'."}
    ],
)
code: str = response.choices[0].message.content
if code:
    print(code)
    with cillow.Client.new() as client:
        print(client.run_code(code))
```

## CrewAI

[CrewAI](https://github.com/crewAIInc/crewAI) is a platform for building AI agents.

```python
# pip install crewai crewai[tools] cillow
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

@tool("Python interpreter tool")
def execute_python(code: str):
    """
    Execute Python code and return the results.
    """
    with cillow.Client.new() as client:
        return client.run_code(code)

# Define the agent
python_executor = Agent(
    role='Python Executor',
    goal='Execute Python code and return the results',
    backstory="You are a helpful assistant that can execute python code in a Jupyter notebook.",
    tools=[execute_python],
    llm=LLM(model="groq/llama-3.3-70b-versatile")
)

# Define the task
execute_task = Task(
    description="Calculate how many r's are in the word 'strawberry'",
    agent=python_executor,
    expected_output="The number of r's in the word 'strawberry'"
)

# Create the crew
code_execution_crew = Crew(
    agents=[python_executor],
    tasks=[execute_task],
    verbose=True,
)

# Run the crew
result = code_execution_crew.kickoff()
print(result)
```

## LlamaIndex

[LlamaIndex](https://github.com/run-llama/llama_index) is a data framework for your LLM applications

```python
# pip install llama-index cillow
from llama_index.core.tools import FunctionTool
from llama_index.llms.groq import Groq
from llama_index.core.agent import ReActAgent

# Define the tool
def execute_python(code: str):
    with cillow.Client.new() as client:
        return client.run_code(code)

e2b_sandbox_tool = FunctionTool.from_defaults(
    name="execute_python",
    description="Execute python code in a Jupyter notebook cell and return result",
    fn=execute_python
)

# Initialize LLM
llm = Groq(model="llama-3.3-70b-versatile")

# Initialize ReAct agent
agent = ReActAgent.from_tools([e2b_sandbox_tool], llm=llm, verbose=True)
agent.chat("Calculate how many r's are in the word 'strawberry'")
```

## LangChain

Build context-aware reasoning applications with [LangChain](https://github.com/langchain-ai/langchain)

```python
# pip install langchain langchain-groq cillow
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_groq import ChatGroq

INSTRUCTION = "You are a helpful assistant that can execute python code in a Jupyter notebook."

# Define the tool
@tool
def execute_python(code: str):
    """
    Execute python code in a Jupyter notebook.
    """
    with cillow.Client.new() as client:
        return client.run_code(code)

# Define LangChain components
prompt_template = ChatPromptTemplate.from_messages([
    ("system", INSTRUCTION),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

tools = [execute_python]
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

agent = create_tool_calling_agent(llm, tools, prompt_template)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Run the agent
agent_executor.invoke({"input": "Calculate how many r's are in the word 'strawberry'"})
```
