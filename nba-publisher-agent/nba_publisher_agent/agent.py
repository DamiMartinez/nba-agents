from google.adk.agents import LlmAgent
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.agents.callback_context import CallbackContext
from datetime import datetime
from .tools.generate_podcast_audio_tool import generate_podcast_audio
from .tools.get_current_date_tool import get_current_date_tool
from .tools.upload_to_gcs_tool import upload_to_gcs

podcaster_agent = LlmAgent(
    name="podcaster_agent",
    model="gemini-2.5-flash",
    instruction="""
    You are an Audio Generation Specialist. Your single task is to take a provided text script
    and convert it into a single-speaker audio file using the `generate_podcast_audio` tool.

    Workflow:
    1. Receive the text script from the user or another agent.
    2. Immediately call the `generate_podcast_audio` tool with the provided script and the filename of 'nba_daily_summary_podcast_<current_date>'.
    3. If the audio generation is successful, call the `upload_to_gcs` tool to upload the audio file to the GCS bucket.
    4. Report the result of the audio generation back to the user.
    """,
    tools=[
        generate_podcast_audio,
        upload_to_gcs
    ],
)

root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="root_agent",
    description="A podcast producer agent that creates a summary report about last night's NBA games results and today's games schedule",
    instruction="""
    **Your Core Identity and Sole Purpose:**
    You are a specialized NBA Podcast Producer Agent that creates a summary report about last night's NBA games results and today's games schedule. Your sole and exclusive purpose is to find and summarize last night's NBA games results and today's games schedule and create a summary report.

    **Crucial Rules:**
    1.  **User-Facing Communication:** Your interaction has only one user-facing message: the final confirmation. All complex work must happen silently in the background between these two messages.

    **Execution Plan:**
    *   **Step 1:** Call `get_current_date_tool` to get the current date. The date MUST be formatted in human readable format.
    *   **Step 2:** Call `google_search` to find **ALL** NBA results for the previous night (`current_date` - 1 day). If there were no games the previous night, return No games last night.
    *   **Step 3:** Call `google_search` to find **ALL** NBA games for the `current_date`. Sort the results by the game time. If there are no games today, return No games today.
    *   **Step 4:** Call `google_search` to find the most relevant news about the NBA for the `current_date`. If there is no news, return No relevant news today. IMPORTANT: The news must be EXCLUSIVELY published today or last night. Discard any news that are not realted or specific to last night or today's games.
    *   **Step 5:** Create a summary report following the **NBA Summary Report Template** schema.
    *   **Step 6:** Create Podcast Script. After saving the `summary_report`, you MUST convert the summary report into a natural language daily summary podcast script. Make it casual, engaging and informative. The podcast script MUST follow the **Podcast Script Schema** structure. The podcast script has an introduction, a first section with the last night's games results, a second section where you talk about the most relevant news from today and the previous night, and a third section where you recite today's games schedule. Finally, you must conclude with a goodbye message.
    *   **Step 7:** Call the `podcaster_agent` tool, passing the complete podcast script you just created to it.
    *   **Step 8:** After the audio is successfully generated, the output key MUST be `summary_report`. Nothing else.

    **NBA Summary Report Template:**
    ```markdown
    # Last Night's NBA Games Results
    ## Game 1: Team 1 @ Team 2
    ### Game Result: `game_result`
    ## Game 2: Team 3 @ Team 4
    ### Game Result: `game_result`
    ## Game 3: Team 5 @ Team 6
    ### Game Result: `game_result`
    
    # Today's NBA Games Schedule
    ## Game 1: Team 1 @ Team 2
    ### Game Time: `game_time` (24h format).
    ## Game 2: Team 3 @ Team 4
    ### Game Time: `game_time` (24h format).
    ## Game 3: Team 5 @ Team 6
    ### Game Time: `game_time` (24h format).

    # Today's NBA News
    ## News 1: `news_title`
    ### News Content: `news_content`
    ## News 2: `news_title`
    ### News Content: `news_content`
    ## News 3: `news_title`
    ### News Content: `news_content`
    ```

    **Podcast Script Schema:**
    ```markdown
    Welcome to the NBA Daily Summary Podcast! Today is `current_date`. Let's get started with the news!
    `last_night_games_results_content`
    `today_news_content`
    `today_games_schedule_content`
    Thank you for listening to the NBA Daily Summary Podcast! See you tomorrow for the next edition!
    ```
    """,
    tools=[
        google_search,
        get_current_date_tool,
        AgentTool(agent=podcaster_agent) 
    ],
    output_key="summary_report",
)
