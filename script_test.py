import asyncio, json
from mcp_server import Tools, send_notification
async def main():
    tools = Tools(send_notification)
    result = await tools.get_website('https://steve-yegge.medium.com/the-anthropic-hive-mind-d01f768f3d7b')
    print(json.dumps(result, indent=2)[:500])
asyncio.run(main())
