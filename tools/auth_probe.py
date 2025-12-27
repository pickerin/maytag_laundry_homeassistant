import asyncio

async def main():
    # We don’t know your exact installed module layout yet, so we introspect.
    import whirlpool
    print("whirlpool package:", whirlpool)
    print("whirlpool attrs:", [a for a in dir(whirlpool) if "Auth" in a or "Client" in a or "Session" in a])

if __name__ == "__main__":
    asyncio.run(main())
