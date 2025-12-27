import asyncio
import websockets

async def chat():
    async with websockets.connect(
        "ws://localhost:8000/ws/conversation",
        ping_interval=20,    # Keep pings going
        ping_timeout=120,    # Allow up to 2 minutes without response 
    ) as ws:
        while True:
            message = input("You: ")
            if message.lower() == "exit":
                break
            await ws.send(message)
            response = ""
            async for msg in ws:
                if "\n\n" in msg:  # End marker from your server
                    response += msg.replace("\n\n", "")
                    print( response)
                    break
                else:
                    response += msg
                    #print(msg, end="", flush=True)

asyncio.run(chat())