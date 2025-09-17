import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import threading

class DatabaseManager:
    def __init__(self, db_path: str = "database/creator_coaches.db"):
        self.db_path = db_path
        self._local = threading.local()  # Thread-local storage for connections
        self.init_database()

    def get_connection(self):
        """Get thread-safe database connection"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            # Enable WAL mode for better concurrency
            self._local.connection.execute('PRAGMA journal_mode=WAL')
        return self._local.connection

    def init_database(self):
        """Initialize database with all required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Creators table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS creators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                platform TEXT NOT NULL,
                display_name TEXT,
                bio TEXT,
                follower_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_scraped TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')

        # Posts table with comprehensive metrics
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                post_id TEXT UNIQUE NOT NULL,
                post_type TEXT NOT NULL,
                caption_text TEXT,
                transcript TEXT,
                media_url TEXT,
                post_date TIMESTAMP,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                engagement_rate REAL,
                hashtags TEXT,
                mentions TEXT,
                duration INTEGER,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_id) REFERENCES creators (id)
            )
        ''')

        # Coach profiles generated from analysis
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coach_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                expertise_areas TEXT,
                frameworks TEXT,
                teaching_style TEXT,
                signature_phrases TEXT,
                key_results TEXT,
                system_prompt TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_id) REFERENCES creators (id)
            )
        ''')

        # Knowledge base chunks for RAG
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                post_id INTEGER,
                chunk_text TEXT,
                chunk_type TEXT,
                topic_tags TEXT,
                embedding_vector BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_id) REFERENCES creators (id),
                FOREIGN KEY (post_id) REFERENCES posts (id)
            )
        ''')

        # Chat sessions for tracking conversations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                session_title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_id) REFERENCES creators (id)
            )
        ''')

        # Individual messages in chat sessions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                message_type TEXT,
                content TEXT,
                referenced_chunks TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES chat_sessions (id)
            )
        ''')

        # Add indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_creator_id ON posts (creator_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_transcript ON posts (creator_id, transcript)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_type ON posts (creator_id, post_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_likes ON posts (creator_id, likes)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_coach_profiles_creator ON coach_profiles (creator_id)')

        conn.commit()
        conn.close()

    def add_creator(self, username: str, platform: str, display_name: str = None, bio: str = None) -> int:
        """Add a new creator to track"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO creators (username, platform, display_name, bio)
            VALUES (?, ?, ?, ?)
        ''', (username, platform, display_name, bio))

        creator_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return creator_id

    def add_post(self, creator_id: int, post_data: Dict) -> int:
        """Add a post with all metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO posts (
                creator_id, post_id, post_type, caption_text, transcript,
                media_url, post_date, likes, comments, shares, views,
                engagement_rate, hashtags, mentions, duration
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            creator_id,
            post_data.get('post_id'),
            post_data.get('post_type'),
            post_data.get('caption_text'),
            post_data.get('transcript'),
            post_data.get('media_url'),
            post_data.get('post_date'),
            post_data.get('likes', 0),
            post_data.get('comments', 0),
            post_data.get('shares', 0),
            post_data.get('views', 0),
            post_data.get('engagement_rate', 0.0),
            json.dumps(post_data.get('hashtags', [])),
            json.dumps(post_data.get('mentions', [])),
            post_data.get('duration', 0)
        ))

        post_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return post_id

    def get_creator_posts(self, creator_id: int) -> List[Dict]:
        """Get all posts for a creator"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM posts WHERE creator_id = ? ORDER BY post_date DESC
        ''', (creator_id,))

        posts = []
        for row in cursor.fetchall():
            post = dict(zip([col[0] for col in cursor.description], row))
            post['hashtags'] = json.loads(post['hashtags'] or '[]')
            post['mentions'] = json.loads(post['mentions'] or '[]')
            posts.append(post)

        conn.close()
        return posts

    def save_coach_profile(self, creator_id: int, profile_data: Dict) -> int:
        """Save generated coach profile"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO coach_profiles (
                creator_id, expertise_areas, frameworks, teaching_style,
                signature_phrases, key_results, system_prompt, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            creator_id,
            json.dumps(profile_data.get('expertise_areas', [])),
            json.dumps(profile_data.get('frameworks', [])),
            str(profile_data.get('teaching_style', '')),
            json.dumps(profile_data.get('signature_phrases', [])),
            json.dumps(profile_data.get('key_results', [])),
            str(profile_data.get('system_prompt', '')),
            datetime.now().isoformat()
        ))

        profile_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return profile_id

    def get_coach_profile(self, creator_id: int) -> Optional[Dict]:
        """Get coach profile for a creator"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get both coach profile and creator info
        cursor.execute('''
            SELECT cp.*, c.username
            FROM coach_profiles cp
            JOIN creators c ON cp.creator_id = c.id
            WHERE cp.creator_id = ?
        ''', (creator_id,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        profile = dict(zip([col[0] for col in cursor.description], row))
        profile['expertise_areas'] = json.loads(profile['expertise_areas'] or '[]')
        profile['frameworks'] = json.loads(profile['frameworks'] or '[]')
        profile['signature_phrases'] = json.loads(profile['signature_phrases'] or '[]')
        profile['key_results'] = json.loads(profile['key_results'] or '[]')

        # Add creator_username for compatibility
        profile['creator_username'] = profile['username']

        conn.close()
        return profile

    def add_knowledge_chunk(self, creator_id: int, post_id: int, chunk_data: Dict) -> int:
        """Add a knowledge chunk for RAG"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO knowledge_chunks (
                creator_id, post_id, chunk_text, chunk_type, topic_tags, embedding_vector
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            creator_id,
            post_id,
            chunk_data.get('chunk_text'),
            chunk_data.get('chunk_type'),
            json.dumps(chunk_data.get('topic_tags', [])),
            chunk_data.get('embedding_vector')
        ))

        chunk_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return chunk_id

    def delete_creator_knowledge_chunks(self, creator_id: int) -> bool:
        """Delete all knowledge chunks for a creator"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM knowledge_chunks WHERE creator_id = ?', (creator_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deleting knowledge chunks for creator {creator_id}: {e}")
            return False

    def get_creators(self) -> List[Dict]:
        """Get all creators"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM creators WHERE is_active = 1')
        creators = []
        for row in cursor.fetchall():
            creators.append(dict(zip([col[0] for col in cursor.description], row)))

        conn.close()
        return creators

    def get_creator_post_stats(self, creator_id: int) -> Dict:
        """Get post statistics for a creator efficiently"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                COUNT(*) as total_posts,
                COUNT(CASE WHEN transcript IS NOT NULL AND transcript != '' THEN 1 END) as transcribed_posts,
                COUNT(CASE WHEN post_type = 'video' THEN 1 END) as video_posts
            FROM posts
            WHERE creator_id = ?
        ''', (creator_id,))

        result = cursor.fetchone()

        # Get knowledge base statistics
        cursor.execute('''
            SELECT
                COUNT(DISTINCT post_id) as knowledge_transcriptions,
                COUNT(*) as knowledge_chunks
            FROM knowledge_chunks
            WHERE creator_id = ?
        ''', (creator_id,))

        knowledge_result = cursor.fetchone()
        # Don't close connection - reuse it

        return {
            "total_posts": result[0] if result else 0,
            "transcribed_posts": result[1] if result else 0,
            "video_posts": result[2] if result else 0,
            "knowledge_transcriptions": knowledge_result[0] if knowledge_result else 0,
            "knowledge_chunks": knowledge_result[1] if knowledge_result else 0
        }

    def delete_post(self, post_id: str) -> bool:
        """Delete a post by post_id"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Also delete associated knowledge chunks
        cursor.execute('DELETE FROM knowledge_chunks WHERE post_id IN (SELECT id FROM posts WHERE post_id = ?)', (post_id,))

        # Delete the post
        cursor.execute('DELETE FROM posts WHERE post_id = ?', (post_id,))

        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def delete_creator(self, creator_id: int) -> bool:
        """Delete a creator and all associated data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Delete in order due to foreign key constraints
        cursor.execute('DELETE FROM knowledge_chunks WHERE creator_id = ?', (creator_id,))
        cursor.execute('DELETE FROM coach_profiles WHERE creator_id = ?', (creator_id,))
        cursor.execute('DELETE FROM posts WHERE creator_id = ?', (creator_id,))
        cursor.execute('DELETE FROM creators WHERE id = ?', (creator_id,))

        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def update_post_transcript(self, post_id: str, transcript: str) -> bool:
        """Update a post's transcript"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('UPDATE posts SET transcript = ? WHERE post_id = ?', (transcript, post_id))

        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated