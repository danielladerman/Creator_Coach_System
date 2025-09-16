# Creator Coach System

Transform your favorite creators into AI coaches based on their actual content, frameworks, and proven results.

## 🎯 Overview

This system scrapes creator content from Instagram, transcribes videos, analyzes their expertise and teaching style, then creates AI coaches that give authentic advice based on their real methods - not generic responses.

**Example**: Ask a social media coach "How do I grow my page?" and get "My Hook-Value-CTA framework from post #23 that got 50K views" instead of generic advice.

## 🏗️ Architecture

```
Data Flow: Scrape → Transcribe → Analyze → Generate Coach Profile → Chunk & Embed → Coach Creation
```

### Core Components

1. **Content Scraping** - Extract Instagram posts with full metrics
2. **Transcription System** - Convert video/audio to text using OpenAI Whisper
3. **Content Analysis Agent** - Extract expertise, frameworks, and teaching style
4. **RAG Knowledge Base** - Chunk content by strategy/topic with semantic search
5. **AI Coach Creation** - Generate authentic coaches with analysis-based prompts
6. **Web Interface** - Clean Flask UI for management and chat

## 🚀 Quick Start

### 1. Setup Environment

```bash
cd creator-coach-system
pip install -r requirements.txt
```

### 2. Configure API Keys

Copy `.env.example` to `.env` and add your keys:

```env
OPENAI_API_KEY=your_openai_api_key_here
APIFY_API_TOKEN=your_apify_api_token_here
```

### 3. Run Complete Pipeline

```bash
python main.py
```

This will:
- Scrape @personalbrandlaunch (or your chosen creator)
- Transcribe all video content
- Analyze expertise and frameworks
- Create authentic AI coach
- Start interactive chat

### 4. Launch Web Interface

```bash
python web_ui/app.py
```

Visit `http://localhost:5000` for the full web interface.

## 📁 Project Structure

```
creator-coach-system/
├── scrapers/           # Instagram content scraping (Apify)
├── transcription/      # Video → text with OpenAI Whisper
├── analysis/          # Content analysis for authentic profiles
├── knowledge_base/     # RAG system with FAISS + embeddings
├── coaches/           # AI coach creation and management
├── web_ui/            # Flask interface
├── database/          # SQLite storage and models
├── config/            # Settings and API keys
├── main.py            # Complete pipeline script
└── requirements.txt   # Dependencies
```

## 🔍 How It Works

### 1. Content Scraping (Instagram)
- Uses Apify actors for reliable Instagram scraping
- Extracts posts, captions, videos, and full engagement metrics
- Stores hashtags, mentions, post timing, and media URLs

### 2. Video Transcription
- Downloads videos temporarily for processing
- Transcribes with OpenAI Whisper (high accuracy)
- Extracts duration and stores transcript text
- Cleans up video files after processing

### 3. Content Analysis (The Key Component)
```python
# Analyzes ALL content to extract:
expertise_areas = [...]        # Real areas they demonstrate expertise
frameworks = [...]             # Specific methods they actually use
teaching_style = {...}         # Their authentic communication patterns
signature_phrases = [...]      # Exact phrases they repeatedly use
key_results = [...]            # Metrics and achievements they've shared
```

### 4. RAG Knowledge Base
- Chunks content by strategy, framework, and topic
- Uses OpenAI embeddings for semantic search
- FAISS index for fast similarity search
- Preserves post metadata for reference links

### 5. AI Coach Creation
```python
system_prompt = f"""You are {username}, expert in {actual_expertise}.
Your proven strategies include: {specific_frameworks}
Your results: {actual_metrics}
Always reference your real experience and methods."""
```

## 🎯 Key Success Factors

### Authentic Coach Responses
- **No Generic Advice**: Only strategies they've actually taught
- **Real Content References**: "In my post about X, I shared..."
- **Proven Methods**: References actual frameworks and results
- **Authentic Voice**: Uses their signature phrases and style

### Quality Assurance
- Analysis extracts ONLY what's present in content
- System prompts ensure first-person authentic responses
- RAG system provides relevant context for each answer
- Comprehensive metrics tracking for content verification

## 🛠️ Development

### Add New Creator
```python
# Via code
scraper = InstagramScraper(apify_token)
result = scraper.scrape_profile('username', max_posts=50)

# Via web interface
# Visit /scrape and enter username
```

### Chat with Coach
```python
coach_manager = CoachManager(openai_key, db, rag_system)
coach = coach_manager.load_coach(creator_id)
response = coach.ask_coach("Your question here")
```

### Access Knowledge Base
```python
rag_system = RAGKnowledgeBase(openai_key)
rag_system.load_knowledge_base(creator_id)
results = rag_system.search_knowledge("search query", k=5)
```

## 📊 Database Schema

### Creators
- Username, platform, bio, follower count
- Scraping status and timestamps

### Posts
- Full content (caption, transcript, media URL)
- Complete metrics (likes, comments, views, engagement rate)
- Hashtags, mentions, post timing
- Link to original content

### Coach Profiles
- Extracted expertise areas and frameworks
- Teaching style and signature phrases
- Generated system prompts
- Analysis metadata

### Knowledge Chunks
- Strategy-based content chunking
- Topic tags and embeddings
- Post references and metadata

## 🔧 Configuration

### Scraping Settings
```env
MAX_VIDEO_SIZE_MB=100           # Skip large videos
TEMP_DOWNLOAD_DIR=temp_downloads # Temporary storage
```

### OpenAI Settings
```env
OPENAI_API_BASE=https://api.openai.com/v1  # Custom endpoint if needed
```

### Database
```env
DATABASE_URL=sqlite:///database/creator_coaches.db
```

## 🎮 Example Usage

```bash
# Quick test with personalbrandlaunch
python main.py
# Enter: personalbrandlaunch
# Enter: 25

# Full analysis
python main.py
# Enter: your_target_creator
# Enter: 100

# Web interface
python web_ui/app.py
# Visit http://localhost:5000
```

## 🤝 Contributing

1. Focus on authentic coach responses based on real content
2. Improve content analysis for better expertise extraction
3. Add support for additional social platforms
4. Enhance RAG system for more relevant context

## 📝 License

Built for creating authentic AI coaches from real creator content. Focus on defensive use cases and respect creator intellectual property.

---

**Next Steps**: Start with @personalbrandlaunch to test the system, then expand to your favorite creators!