# Real-time contact center AI agent simulation using LangChain (updated for recent versions ~1.x)
# Uses ReAct agent pattern with streaming support
# pip install fastapi uvicorn langchain langchain-community langchain-ollama langchain-hub websockets

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from langchain.agents import create_agent
from langchain_core.tools import Tool
from langchain_ollama import ChatOllama

app = FastAPI(title="Real-Time Contact Center AI Agent with Streaming")

# LLM setup 
llm = ChatOllama(
    model="phi4-mini",  
    temperature=0,
)

# Tool

def escalate_to_human(query: str) -> str:
    """Escalate complex or sensitive issues to a human agent."""
    return f"I've escalated your issue: '{query}'. A human agent will assist you shortly."


tools = [
    Tool(
        name="escalateToHuman",
        func=escalate_to_human,
        description="Use this tool to escalate complex or sensitive issues to a human agent. Input: the customer query or issue description."
    )
]



system_prompt = """
You are an empathetic contact center AI agent.
- Always acknowledge the customer's situation with compassion
- Offer general info about payment extensions, flexible plans, and hardship programs
- ONLY escalate to human if the customer asks for specific account details, disputes, or complex negotiations
- Otherwise, provide helpful guidance and next steps
Keep responses warm, clear, and concise.
"""

# Create the ReAct agent
agent_executor = create_agent(llm, tools, system_prompt=system_prompt)


@app.websocket("/ws/conversation")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Receive customer message from client
            data = await websocket.receive_text()
            customer_message = data.strip()

            if not customer_message:
                continue

            await websocket.send_text(f"Customer: {customer_message}\nAgent: ")

          
            tool_used = False

            async for event in agent_executor.astream_events(
                {"input": customer_message},
                version="v2",  
            ):
                kind = event["event"]

                if kind == "on_chat_model_stream":  # LA new token from the LLM (this is what streams the visible response)
                    chunk = event["data"]["chunk"]
                    if token := chunk.content:
                        await websocket.send_text(token)
                elif kind == "on_tool_start": #Agent is about to call a tool (e.g., escalate_to_human)
                    tool_used = True
                    await websocket.send_text(
                        "\n\nOne moment please — I'm connecting you to a human agent who can better assist with payment plans and extensions."
                    )
                # Tool end — show result (escalation confirmation)
                elif kind == "on_tool_end":
                    tool_output = event["data"]["output"]
                    await websocket.send_text(f"\n\n{tool_output}")
                # If no tool was used, add clean line break
            if not tool_used:
                await websocket.send_text("\n\n")

            
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        await websocket.send_text(f"\nError: {str(e)}\n")
        await websocket.close()


@app.get("/")
async def root():
    return {"message": "Contact Center AI Agent WebSocket server running. Connect to /ws/conversation"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("callCenter:app", reload=True)


 # Ensure Ollama is running and the model is pulled: ollama run mistral-small

