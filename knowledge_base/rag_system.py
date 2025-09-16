import openai
import numpy as np
import faiss
import pickle
import json
from typing import List, Dict, Tuple, Optional
from sentence_transformers import SentenceTransformer
import tiktoken

class RAGKnowledgeBase:
    """
    RAG system for creator coach knowledge base
    Chunks content by strategy/topic and enables semantic search
    """

    def __init__(self, openai_api_key: str, database_manager=None, embedding_model: str = "text-embedding-ada-002"):
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        self.embedding_model = embedding_model
        self.db = database_manager

        # Initialize sentence transformer for backup embeddings
        self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')

        # FAISS index for vector search
        self.index = None
        self.chunk_metadata = []
        self.embedding_dimension = 1536  # OpenAI ada-002 dimension

        # Token counter for chunk sizing
        self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

    def create_knowledge_base(self, creator_id: int, posts: List[Dict], coach_profile: Dict) -> Dict:
        """
        Create comprehensive knowledge base from creator content
        """
        print(f"Creating knowledge base for creator {creator_id}...")

        # Step 1: Chunk content strategically
        all_chunks = self._chunk_content_strategically(posts, coach_profile)

        # Step 2: Generate embeddings
        embeddings = self._generate_embeddings(all_chunks)

        # Step 3: Save chunks to database
        if self.db:
            self._save_chunks_to_database(creator_id, all_chunks, embeddings)

        # Step 4: Build FAISS index
        self._build_faiss_index(embeddings, all_chunks, creator_id)

        # Step 5: Save knowledge base
        self._save_knowledge_base(creator_id)

        print(f"✓ Knowledge base created with {len(all_chunks)} chunks")
        return {
            "creator_id": creator_id,
            "total_chunks": len(all_chunks),
            "chunk_types": list(set([chunk["chunk_type"] for chunk in all_chunks])),
            "embedding_dimension": self.embedding_dimension
        }

    def _chunk_content_strategically(self, posts: List[Dict], coach_profile: Dict) -> List[Dict]:
        """
        Optimized content chunking for better semantic search
        """
        chunks = []

        for post in posts:
            post_chunks = []

            # Strategy 1: Caption content chunking
            if post.get('caption_text'):
                caption_chunks = self._chunk_semantically(
                    post['caption_text'],
                    post,
                    "caption"
                )
                post_chunks.extend(caption_chunks)

            # Strategy 2: Transcript content chunking (most valuable for RAG)
            if post.get('transcript'):
                transcript_chunks = self._chunk_semantically(
                    post['transcript'],
                    post,
                    "transcript"
                )
                post_chunks.extend(transcript_chunks)

            # Strategy 3: High-engagement posts get priority chunking
            if post.get('likes', 0) > 1000 or post.get('engagement_rate', 0) > 500:
                engagement_chunk = self._create_high_value_chunk(post)
                if engagement_chunk:
                    post_chunks.append(engagement_chunk)

            chunks.extend(post_chunks)

        return chunks

    def _chunk_semantically(self, content: str, post: Dict, content_type: str) -> List[Dict]:
        """
        Semantic chunking optimized for RAG search
        """
        chunks = []

        # Smart chunking based on content length and type
        if content_type == "transcript":
            # For transcripts, use paragraph-based chunking for better coherence
            chunk_size = 200  # tokens per chunk for transcripts
        else:
            # For captions, use smaller chunks since they're typically shorter
            chunk_size = 100  # tokens per chunk for captions

        # Split into semantic chunks
        chunk_texts = self._chunk_by_tokens(content, chunk_size)

        for i, chunk_text in enumerate(chunk_texts):
            if len(chunk_text.strip()) < 20:  # Skip very short chunks
                continue

            chunk = {
                "chunk_text": chunk_text.strip(),
                "chunk_type": f"semantic_{content_type}",
                "topic_tags": [content_type],
                "post_metadata": self._extract_post_metadata(post),
                "chunk_index": i,
                "content_quality": self._assess_content_quality(chunk_text, post)
            }
            chunks.append(chunk)

        return chunks

    def _assess_content_quality(self, text: str, post: Dict) -> float:
        """
        Simple content quality assessment for ranking chunks
        """
        quality_score = 0.0

        # Length factor (not too short, not too long)
        text_length = len(text.split())
        if 15 <= text_length <= 150:
            quality_score += 0.3

        # Engagement factor
        likes = post.get('likes', 0)
        if likes > 1000:
            quality_score += 0.4
        elif likes > 500:
            quality_score += 0.2

        # Content richness (questions, actionable advice)
        if '?' in text:
            quality_score += 0.1
        if any(word in text.lower() for word in ['how to', 'tip', 'strategy', 'step']):
            quality_score += 0.2

        return min(quality_score, 1.0)

    def _create_high_value_chunk(self, post: Dict) -> Optional[Dict]:
        """
        Create prioritized chunk for high-engagement content
        """
        if not post.get('caption_text') and not post.get('transcript'):
            return None

        # Prefer transcript over caption for high-value content
        content = post.get('transcript') or post.get('caption_text')

        return {
            "chunk_text": content,
            "chunk_type": "high_value",
            "topic_tags": ["viral", "high_engagement"],
            "post_metadata": self._extract_post_metadata(post),
            "engagement_metrics": {
                "likes": post.get('likes', 0),
                "comments": post.get('comments', 0),
                "engagement_rate": post.get('engagement_rate', 0)
            },
            "content_quality": 1.0  # Max quality for high-engagement content
        }

    def _chunk_by_strategy(self, content: str, post: Dict, content_type: str, frameworks: List, expertise_areas: List) -> List[Dict]:
        """
        Chunk content based on identified strategies and frameworks
        """
        chunks = []

        # Split content into sentences for strategic chunking
        sentences = content.split('. ')

        # Strategy 1: Framework-based chunking
        for framework in frameworks:
            framework_content = self._extract_framework_content(sentences, framework)
            if framework_content:
                chunks.append({
                    "chunk_text": framework_content,
                    "chunk_type": f"framework_{content_type}",
                    "topic_tags": [framework['name'], content_type],
                    "post_metadata": self._extract_post_metadata(post),
                    "framework_reference": framework['name'],
                    "expertise_area": self._match_expertise_area(framework_content, expertise_areas)
                })

        # Strategy 2: Topic-based chunking
        for area in expertise_areas:
            topic_content = self._extract_topic_content(sentences, area)
            if topic_content:
                chunks.append({
                    "chunk_text": topic_content,
                    "chunk_type": f"expertise_{content_type}",
                    "topic_tags": [area, content_type],
                    "post_metadata": self._extract_post_metadata(post),
                    "expertise_area": area
                })

        # Strategy 3: General chunking for remaining content
        if not chunks:  # If no specific strategies matched, create general chunks
            chunk_size = 300  # tokens
            general_chunks = self._chunk_by_tokens(content, chunk_size)

            for chunk_text in general_chunks:
                chunks.append({
                    "chunk_text": chunk_text,
                    "chunk_type": f"general_{content_type}",
                    "topic_tags": [content_type],
                    "post_metadata": self._extract_post_metadata(post),
                    "expertise_area": "general"
                })

        return chunks

    def _extract_framework_content(self, sentences: List[str], framework: Dict) -> str:
        """Extract sentences related to a specific framework"""
        framework_name = framework['name'].lower()
        framework_keywords = framework.get('key_components', [])

        relevant_sentences = []

        for sentence in sentences:
            sentence_lower = sentence.lower()
            if (framework_name in sentence_lower or
                any(keyword.lower() in sentence_lower for keyword in framework_keywords)):
                relevant_sentences.append(sentence.strip())

        return '. '.join(relevant_sentences) if relevant_sentences else ""

    def _extract_topic_content(self, sentences: List[str], expertise_area: str) -> str:
        """Extract sentences related to expertise area"""
        area_keywords = expertise_area.lower().split()
        relevant_sentences = []

        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(keyword in sentence_lower for keyword in area_keywords):
                relevant_sentences.append(sentence.strip())

        return '. '.join(relevant_sentences) if relevant_sentences else ""

    def _chunk_by_tokens(self, text: str, max_tokens: int) -> List[str]:
        """Chunk text by token count"""
        tokens = self.encoding.encode(text)
        chunks = []

        for i in range(0, len(tokens), max_tokens):
            chunk_tokens = tokens[i:i + max_tokens]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text)

        return chunks

    def _create_engagement_chunk(self, post: Dict) -> Optional[Dict]:
        """Create special chunk for high-engagement posts"""
        if not post.get('caption_text') and not post.get('transcript'):
            return None

        content = post.get('transcript') or post.get('caption_text')

        return {
            "chunk_text": content,
            "chunk_type": "high_engagement",
            "topic_tags": ["viral", "high_engagement"],
            "post_metadata": self._extract_post_metadata(post),
            "engagement_metrics": {
                "likes": post.get('likes', 0),
                "comments": post.get('comments', 0),
                "engagement_rate": post.get('engagement_rate', 0)
            }
        }

    def _extract_post_metadata(self, post: Dict) -> Dict:
        """Extract relevant metadata from post"""
        return {
            "post_id": post.get('post_id'),
            "post_type": post.get('post_type'),
            "post_date": post.get('post_date'),
            "likes": post.get('likes', 0),
            "comments": post.get('comments', 0),
            "hashtags": post.get('hashtags', []),
            "media_url": post.get('media_url')
        }

    def _match_expertise_area(self, content: str, expertise_areas: List[str]) -> str:
        """Match content to most relevant expertise area"""
        content_lower = content.lower()

        for area in expertise_areas:
            if area.lower() in content_lower:
                return area

        return "general"

    def _generate_embeddings(self, chunks: List[Dict]) -> np.ndarray:
        """Generate embeddings for all chunks"""
        print("Generating embeddings...")

        texts = [chunk["chunk_text"] for chunk in chunks]
        embeddings = []

        # Use OpenAI embeddings in batches
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            try:
                response = self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=batch
                )

                batch_embeddings = [data.embedding for data in response.data]
                embeddings.extend(batch_embeddings)

            except Exception as e:
                print(f"OpenAI embedding failed, using sentence transformer: {e}")
                # Fallback to sentence transformer
                batch_embeddings = self.sentence_model.encode(batch)
                embeddings.extend(batch_embeddings.tolist())

        return np.array(embeddings, dtype='float32')

    def _build_faiss_index(self, embeddings: np.ndarray, chunks: List[Dict], creator_id: int):
        """Build FAISS index for fast similarity search"""
        print("Building FAISS index...")

        # Create FAISS index
        self.index = faiss.IndexFlatIP(embeddings.shape[1])  # Inner product for cosine similarity

        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)

        # Add embeddings to index
        self.index.add(embeddings)

        # Store chunk metadata
        self.chunk_metadata = chunks

        print(f"✓ FAISS index built with {self.index.ntotal} vectors")

    def _save_chunks_to_database(self, creator_id: int, chunks: List[Dict], embeddings: np.ndarray):
        """Save knowledge chunks to database"""
        if not self.db:
            return

        print("Saving knowledge chunks to database...")

        # Clear existing chunks for this creator
        self.db.delete_creator_knowledge_chunks(creator_id)

        # Save each chunk with its embedding
        saved_count = 0
        for i, chunk in enumerate(chunks):
            try:
                # Find the associated post
                post_id = None
                post_id_str = chunk.get('post_metadata', {}).get('post_id')
                if post_id_str:
                    # Get the database post ID from post_id string
                    posts = self.db.get_creator_posts(creator_id)
                    for post in posts:
                        if post['post_id'] == post_id_str:
                            post_id = post['id']  # Database ID
                            break

                if post_id is None:
                    print(f"Warning: Could not find post_id for chunk {i}")
                    continue

                # Prepare chunk data with embedding
                chunk_data = {
                    'chunk_text': chunk['chunk_text'],
                    'chunk_type': chunk['chunk_type'],
                    'topic_tags': chunk.get('topic_tags', []),
                    'embedding_vector': embeddings[i].tolist()  # Convert numpy array to list
                }

                # Save to database
                self.db.add_knowledge_chunk(creator_id, post_id, chunk_data)
                saved_count += 1

            except Exception as e:
                print(f"Error saving chunk {i}: {str(e)}")

        print(f"✓ Saved {saved_count} knowledge chunks to database")

    def _save_knowledge_base(self, creator_id: int):
        """Save knowledge base to disk"""
        kb_dir = f"knowledge_base/creator_{creator_id}"
        import os
        os.makedirs(kb_dir, exist_ok=True)

        # Save FAISS index
        faiss.write_index(self.index, f"{kb_dir}/faiss_index.bin")

        # Save metadata
        with open(f"{kb_dir}/chunk_metadata.json", 'w') as f:
            json.dump(self.chunk_metadata, f, indent=2)

        print(f"✓ Knowledge base saved to {kb_dir}")

    def load_knowledge_base(self, creator_id: int) -> bool:
        """Load existing knowledge base"""
        kb_dir = f"knowledge_base/creator_{creator_id}"

        try:
            # Load FAISS index
            self.index = faiss.read_index(f"{kb_dir}/faiss_index.bin")

            # Load metadata
            with open(f"{kb_dir}/chunk_metadata.json", 'r') as f:
                self.chunk_metadata = json.load(f)

            print(f"✓ Knowledge base loaded for creator {creator_id}")
            return True

        except Exception as e:
            print(f"Error loading knowledge base: {e}")
            return False

    def search_knowledge(self, query: str, k: int = 5) -> List[Dict]:
        """Search knowledge base for relevant chunks"""
        if not self.index:
            return []

        try:
            # Generate query embedding
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=[query]
            )
            query_embedding = np.array([response.data[0].embedding], dtype='float32')

        except:
            # Fallback to sentence transformer
            query_embedding = np.array([self.sentence_model.encode([query])[0]], dtype='float32')

        # Normalize query embedding
        faiss.normalize_L2(query_embedding)

        # Search index
        scores, indices = self.index.search(query_embedding, k)

        # Return results with metadata, prioritizing quality
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.chunk_metadata):
                result = self.chunk_metadata[idx].copy()
                result['similarity_score'] = float(score)

                # Boost score for high-quality content
                content_quality = result.get('content_quality', 0.5)
                result['final_score'] = float(score) + (content_quality * 0.1)

                results.append(result)

        # Sort by final score (similarity + quality boost)
        results.sort(key=lambda x: x['final_score'], reverse=True)

        return results