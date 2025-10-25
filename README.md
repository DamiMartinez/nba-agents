# NBA AI Agents

An AI-powered NBA podcast generation system built with Google's Agent Development Kit (ADK) that automatically creates daily audio summaries of NBA games.

## 🏀 Overview

The system consists of two main agents that work together to gather NBA data, create engaging content, produce audio using Gemini's TTS, and distribute automatically via RSS feed to Spotify.

## 🎧 Live Podcast

**Listen to the NBA Daily Summary Podcast:**
- [Spotify](https://open.spotify.com/show/5u255pZEvJeOzKMWCuDQsP)
- [RSS Feed](https://damimartinez.github.io/nba-daily-summary-podcast/podcast/rss.xml)

## 📖 Detailed Technical Blog Post

For a comprehensive breakdown of the architecture, implementation details, and technical deep dive, check out my blog post:

**[How I Built an AI-Generated NBA Podcast with Google's ADK](https://damimartinez.github.io/nba-podcast-using-adk/)**

The blog post covers:
- Multi-agent system architecture
- NBA API integration strategies
- Gemini TTS implementation
- RSS feed automation
- Spotify distribution setup

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Google Cloud Platform account
- Google ADK access
- NBA API access

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/DamiMartinez/nba-agents.git
   cd nba-agents/nba-publisher-agent
   ```

2. **Install dependencies:**
   ```bash
   poetry install
   ```

3. **Set up environment variables:**
   ```bash
   export GOOGLE_API_KEY="your-google-ai-api-key"
   export GOOGLE_CLOUD_PROJECT="your-project-id"
   export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/service-account-key.json"
   ```

4. **Run the agent programmatically:**
   ```bash
   # Method 1: Direct execution
   python run_agent.py
   
   # Method 2: Using poetry
   poetry run python run_agent.py
   
   # Method 3: Interactive Python
   python -c "
   import asyncio
   from run_agent import run_nba_agent
   asyncio.run(run_nba_agent())
   "
   ```

### What the Agent Does

The NBA Publisher Agent performs the following steps programmatically:

1. **Gets current date** (Europe/Madrid timezone)
2. **Fetches last night's NBA results** and top scorers
3. **Searches for additional game highlights** using Google Search
4. **Gets tonight's NBA schedule**
5. **Creates a summary report** following the NBA Summary Report Template
6. **Generates a podcast script** from the summary
7. **Converts the script to audio** using the podcaster agent
8. **Uploads the audio to Google Cloud Storage**

### Output

The agent generates:
- **Text summary**: Saved as `nba_summary_YYYYMMDD_HHMMSS.txt`
- **Audio podcast**: Saved as `nba_daily_summary_podcast_YYYY-MM-DD.wav` in the `audios/` directory
- **Console output**: Shows the agent's progress and final response

### Configuration

The system is configured for Europe/Madrid timezone by default. To modify:

1. Update timezone references in `agent.py`
2. Adjust date formatting in tool functions
3. Modify RSS feed update schedule in GitHub Actions

## 📁 Project Structure

```
nba-agents/
├── nba-publisher-agent/
│   ├── run_agent.py                 # Programmatic execution script
│   ├── nba_publisher_agent/
│   │   ├── agent.py                 # Main agent definitions
│   │   └── tools/
│   │       ├── generate_podcast_audio_tool.py
│   │       ├── get_current_date_tool.py
│   │       ├── get_last_night_results_tool.py
│   │       ├── get_tonight_schedule_tool.py
│   │       └── upload_to_gcs_tool.py
│   ├── audios/                      # Generated audio files
│   └── pyproject.toml              # Dependencies and configuration
└── README.md
```

## 🛠️ Customization

The system is highly customizable:
- **Voice Selection**: Choose from 30 available Gemini TTS voices
- **Content Formatting**: Modify report templates in `agent.py`
- **Timezone**: Currently configured for Europe/Madrid timezone
- **Scheduling**: Adjust GitHub Actions cron schedule for different timing

See the [blog post](https://damimartinez.github.io/nba-podcast-using-adk/) for detailed customization examples.

## 📊 Features

- **Automated Daily Generation**: Runs automatically every morning
- **Multi-Source Data**: Combines NBA API, Google Search, and official NBA endpoints
- **Professional Audio**: High-quality TTS with controllable voice styling
- **Cloud Distribution**: Automatic upload and RSS feed updates
- **Timezone Aware**: Configured for Europe/Madrid timezone
- **Error Handling**: Robust error handling and fallback mechanisms
- **Modular Design**: Easy to extend and customize

## 🔧 Dependencies

### Core Dependencies
- `google-adk` - Agent Development Kit framework
- `google-cloud-aiplatform` - AI Platform integration
- `google-genai` - Gemini TTS capabilities
- `google-cloud-storage` - Cloud storage integration
- `nba_api` - NBA data access
- `requests` - HTTP requests

### Development Dependencies
- `pytest` - Testing framework
- `black` - Code formatting
- `pytest-cov` - Coverage reporting

## 📈 Future Enhancements

- Multiple voice styles for different content types
- Multi-language support (Spanish, etc.)
- Advanced analytics and game predictions
- Social media integration
- Interactive voice features

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Google ADK Course](https://www.deeplearning.ai/short-courses/building-live-voice-agents-with-googles-adk/) by Lavi Nigam and Sita Lakshmi Sangameswaran
- [NBA API](https://github.com/swar/nba_api) by Swar Patel
- [Google Gemini TTS](https://ai.google.dev/gemini-api/docs/speech-generation) for audio generation

## 📞 Contact

**Damian Martinez Carmona**
- Email: damian.martinez.carmona@gmail.com
- GitHub: [@DamiMartinez](https://github.com/DamiMartinez)

---

**Built with ❤️ for NBA fans everywhere**
