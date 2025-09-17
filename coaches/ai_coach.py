import openai
import json
from typing import List, Dict, Optional
from datetime import datetime
import time

class AICoach:
    """
    AI Coach that gives authentic advice based on creator's actual content and expertise
    """

    def __init__(self, openai_api_key: str, creator_id: int, coach_profile: Dict, rag_system, database_manager=None):
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        self.creator_id = creator_id
        self.coach_profile = coach_profile
        self.rag_system = rag_system
        self.db = database_manager
        self.system_prompt = coach_profile.get("system_prompt", "")
        self.conversation_history = []

    def ask_coach(self, question: str, context_chunks: int = 5) -> Dict:
        """
        Ask the coach a question and get an authentic response based on their content
        """
        print(f"Processing question for coach {self.coach_profile['creator_username']}...")

        # Step 1: Search knowledge base for relevant content
        relevant_chunks = self.rag_system.search_knowledge(question, k=context_chunks)

        # Step 2: Build context from relevant chunks
        context = self._build_context_from_chunks(relevant_chunks)

        # Step 3: Generate response using coach's authentic persona
        response = self._generate_coach_response(question, context, relevant_chunks)

        # Step 4: Store conversation
        conversation_entry = {
            "question": question,
            "response": response["answer"],
            "referenced_content": response["references"],
            "timestamp": datetime.now().isoformat()
        }
        self.conversation_history.append(conversation_entry)

        return response

    def _build_context_from_chunks(self, chunks: List[Dict]) -> str:
        """Build context string from relevant knowledge chunks"""
        if not chunks:
            return "No specific relevant content found in your knowledge base."

        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            chunk_context = f"\n--- RELEVANT CONTENT {i} ---\n"
            chunk_context += f"From: {chunk.get('chunk_type', 'content')} "

            # Add post metadata if available
            post_meta = chunk.get('post_metadata', {})
            if post_meta.get('post_id'):
                chunk_context += f"(Post {post_meta['post_id']}"
                if post_meta.get('likes'):
                    chunk_context += f", {post_meta['likes']} likes"
                chunk_context += ")"

            chunk_context += f"\nContent: {chunk['chunk_text']}\n"

            # Add framework reference if available
            if chunk.get('framework_reference'):
                chunk_context += f"Framework: {chunk['framework_reference']}\n"

            # Add expertise area
            if chunk.get('expertise_area'):
                chunk_context += f"Topic: {chunk['expertise_area']}\n"

            context_parts.append(chunk_context)

        return "\n".join(context_parts)

    def _generate_coach_response(self, question: str, context: str, referenced_chunks: List[Dict]) -> Dict:
        """Generate authentic coach response using system prompt and relevant context"""

        # Get creator username for responses
        creator_username = self.coach_profile.get('creator_username', f'creator_{self.creator_id}')

        # Build the prompt with context
        user_prompt = f"""
Based on my actual content and expertise, please answer this question:

QUESTION: {question}

RELEVANT CONTENT FROM MY POSTS:
{context}

Remember to:
1. Answer as me ({creator_username}), in first person
2. Reference specific content, posts, or frameworks when relevant
3. Only give advice based on my actual expertise
4. Use my authentic voice and style
5. If I don't have relevant experience, acknowledge it and redirect to what I do know

Please provide a comprehensive, helpful answer based on my real content and proven methods.
"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )

            answer = response.choices[0].message.content

            # Extract referenced content for transparency
            references = self._extract_references(referenced_chunks)

            return {
                "answer": answer,
                "references": references,
                "context_used": len(referenced_chunks),
                "coach_name": creator_username,
                "expertise_areas": self.coach_profile.get('expertise_areas', [])
            }

        except Exception as e:
            print(f"Error generating coach response: {e}")
            return {
                "answer": f"I'm sorry, I'm having trouble accessing my knowledge right now. Please try again.",
                "references": [],
                "context_used": 0,
                "coach_name": creator_username,
                "error": str(e)
            }

    def _extract_references(self, chunks: List[Dict]) -> List[Dict]:
        """Extract clean references from chunks for transparency"""
        references = []

        for chunk in chunks:
            post_meta = chunk.get('post_metadata', {})

            reference = {
                "content_type": chunk.get('chunk_type', 'content'),
                "post_id": post_meta.get('post_id'),
                "post_date": post_meta.get('post_date'),
                "engagement": {
                    "likes": post_meta.get('likes', 0),
                    "comments": post_meta.get('comments', 0)
                },
                "media_url": post_meta.get('media_url'),
                "topic": chunk.get('expertise_area'),
                "similarity_score": chunk.get('similarity_score', 0)
            }

            if chunk.get('framework_reference'):
                reference['framework'] = chunk['framework_reference']

            references.append(reference)

        return references

    def get_coach_info(self) -> Dict:
        """Get dynamic information about the coach based on actual content"""
        creator_username = self.coach_profile.get('creator_username', f'creator_{self.creator_id}')

        # Get real data from database efficiently if available
        if self.db:
            stats = self.db.get_creator_post_stats(self.creator_id)

            # Get high engagement count with efficient query
            conn = self.db.db_path
            import sqlite3
            db_conn = sqlite3.connect(conn)
            cursor = db_conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM posts WHERE creator_id = ? AND likes > 1000', (self.creator_id,))
            high_engagement_count = cursor.fetchone()[0]
            db_conn.close()

            return {
                "name": creator_username,
                "total_posts": stats['total_posts'],
                "video_posts": stats['video_posts'],
                "transcribed_posts": stats['transcribed_posts'],
                "high_engagement_posts": high_engagement_count,
                "platform": self.coach_profile.get('platform', 'instagram'),
                "description": f"I'm {creator_username}, and I can help you based on insights from my {stats['total_posts']} posts, including {stats['transcribed_posts']} transcribed videos. Ask me anything about my content and experiences!",
                "knowledge_base_size": len(self.rag_system.chunk_metadata) if hasattr(self.rag_system, 'chunk_metadata') else 0,
                "last_updated": self.coach_profile.get('updated_at', 'Recently')
            }
        else:
            # Fallback for when database is not available
            return {
                "name": creator_username,
                "platform": self.coach_profile.get('platform', 'instagram'),
                "description": f"I'm {creator_username}, ready to help you based on my content and experiences!",
                "total_posts": self.coach_profile.get('total_posts', 0),
                "transcribed_posts": self.coach_profile.get('transcribed_posts', 0),
                "knowledge_base_size": len(self.rag_system.chunk_metadata) if hasattr(self.rag_system, 'chunk_metadata') else 0
            }

    def get_conversation_history(self) -> List[Dict]:
        """Get conversation history for this session"""
        return self.conversation_history

    def clear_conversation_history(self):
        """Clear conversation history"""
        self.conversation_history = []

class CoachManager:
    """
    Manages multiple AI coaches and handles coach selection/creation
    """

    def __init__(self, openai_api_key: str, database_manager, rag_system):
        self.openai_api_key = openai_api_key
        self.db = database_manager
        self.rag_system = rag_system
        self.active_coaches = {}  # creator_id -> AICoach instance

        # Simple in-memory cache with TTL
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes

    def load_coach(self, creator_id: int) -> Optional[AICoach]:
        """Load or create coach for a creator"""
        if creator_id in self.active_coaches:
            return self.active_coaches[creator_id]

        # Get coach profile from database
        coach_profile = self.db.get_coach_profile(creator_id)
        if not coach_profile:
            print(f"No coach profile found for creator {creator_id}")
            return None

        # Load knowledge base
        if not self.rag_system.load_knowledge_base(creator_id):
            print(f"No knowledge base found for creator {creator_id}")
            return None

        # Create coach instance
        coach = AICoach(
            self.openai_api_key,
            creator_id,
            coach_profile,
            self.rag_system,
            self.db
        )

        self.active_coaches[creator_id] = coach
        print(f"✓ Coach loaded for creator {creator_id}")
        return coach

    def _get_cache_key(self, key: str) -> str:
        """Generate cache key"""
        return f"coach_cache_{key}"

    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Check if cache entry is still valid"""
        return time.time() - cache_entry['timestamp'] < self._cache_ttl

    def _get_from_cache(self, key: str):
        """Get data from cache if valid"""
        cache_key = self._get_cache_key(key)
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if self._is_cache_valid(entry):
                return entry['data']
            else:
                # Clean up expired cache entry
                del self._cache[cache_key]
        return None

    def _set_cache(self, key: str, data):
        """Set data in cache with timestamp"""
        cache_key = self._get_cache_key(key)
        self._cache[cache_key] = {
            'data': data,
            'timestamp': time.time()
        }

    def get_available_coaches(self) -> List[Dict]:
        """Get list of available coaches with dynamic information (cached & optimized)"""
        # Check cache first
        cached_result = self._get_from_cache('available_coaches')
        if cached_result is not None:
            return cached_result

        creators = self.db.get_creators()
        available_coaches = []

        for creator in creators:
            coach_profile = self.db.get_coach_profile(creator['id'])
            if coach_profile:
                # Get dynamic stats efficiently with single SQL query
                stats = self.db.get_creator_post_stats(creator['id'])

                available_coaches.append({
                    "creator_id": creator['id'],
                    "username": creator['username'],
                    "display_name": creator.get('display_name', creator['username']),
                    "total_posts": stats['total_posts'],
                    "transcribed_posts": stats['transcribed_posts'],
                    "knowledge_transcriptions": stats['knowledge_transcriptions'],
                    "knowledge_chunks": stats['knowledge_chunks'],
                    "platform": creator.get('platform', 'instagram'),
                    "last_updated": coach_profile.get('updated_at')
                })

        # Cache the result
        self._set_cache('available_coaches', available_coaches)
        return available_coaches

    def ask_coach_by_id(self, creator_id: int, question: str) -> Dict:
        """Ask a specific coach a question"""
        coach = self.load_coach(creator_id)
        if not coach:
            return {
                "error": f"Coach not available for creator {creator_id}",
                "available_coaches": self.get_available_coaches()
            }

        return coach.ask_coach(question)

    def ask_coach_by_username(self, username: str, question: str) -> Dict:
        """Ask a coach by username"""
        creators = self.db.get_creators()
        creator_id = None

        for creator in creators:
            if creator['username'].lower() == username.lower():
                creator_id = creator['id']
                break

        if not creator_id:
            return {
                "error": f"No coach found for @{username}",
                "available_coaches": self.get_available_coaches()
            }

        return self.ask_coach_by_id(creator_id, question)