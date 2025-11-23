#!/usr/bin/env python3
"""
NBA Publisher Agent - Programmatic Execution Script

This script sets up the runner and session service for the NBA publisher agent
and executes it programmatically.
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
import dotenv

# Add the current directory to Python path to import the agent
sys.path.append(str(Path(__file__).parent))

# Load environment variables from .env file
dotenv.load_dotenv()

from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai.types import Content, Part
from nba_publisher_agent.agent import root_agent

# Configuration
APP_NAME = "nba_publisher_app"
USER_ID = "nba_user"
SESSION_ID = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

async def run_nba_agent():
    """
    Execute the NBA publisher agent programmatically.
    """
    print(f"Starting NBA Publisher Agent execution at {datetime.now()}")
    print(f"Session ID: {SESSION_ID}")
    
    try:
        # Initialize the session service
        session_service = InMemorySessionService()
        
        # Create a session
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=SESSION_ID
        )
        
        # Initialize the runner with the agent and session service
        runner = Runner(
            agent=root_agent,
            app_name=APP_NAME,
            session_service=session_service
        )
        
        # Define the user input to trigger the agent
        user_input = "Create today's NBA daily summary podcast"
        
        # Create content object
        content = Content(role='user', parts=[Part(text=user_input)])
        
        print(f"Sending request: {user_input}")
        print("Processing...")
        
        # Run the agent
        events = runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=content
        )
        
        # Process the agent's response
        final_response = None
        async for event in events:
            if hasattr(event, 'is_final_response') and event.is_final_response():
                # Check if content exists and has parts before accessing
                if hasattr(event, 'content') and event.content:
                    if hasattr(event.content, 'parts') and event.content.parts:
                        # Extract text from text parts
                        text_parts = [part.text for part in event.content.parts if hasattr(part, 'text') and part.text]
                        if text_parts:
                            final_response = ' '.join(text_parts)
                            print("=" * 80)
                            print("AGENT RESPONSE:")
                            print("=" * 80)
                            print(final_response)
                            print("=" * 80)
            elif hasattr(event, 'content') and event.content:
                # Print intermediate responses
                if hasattr(event.content, 'parts') and event.content.parts:
                    text_parts = [part.text for part in event.content.parts if hasattr(part, 'text') and part.text]
                    if text_parts:
                        print(f"Intermediate: {' '.join(text_parts)}")
                    else:
                        print(f"Intermediate: {type(event.content).__name__} (non-text parts)")
        
        # Check if we got a final response
        if final_response:
            print(f"\n✅ NBA Publisher Agent completed successfully!")
            print(f"Session ID: {SESSION_ID}")
        else:
            print("❌ No final response received from the agent")
            
    except Exception as e:
        print(f"❌ Error running NBA Publisher Agent: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def main():
    """
    Main entry point for the script.
    """
    print("NBA Publisher Agent - Programmatic Execution")
    print("=" * 50)
    
    # Run the agent using asyncio.run() for standalone script execution
    return asyncio.run(run_nba_agent())

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 Script completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Script failed!")
        sys.exit(1)
