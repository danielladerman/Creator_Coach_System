from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# Import our custom modules
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import DatabaseManager
from scrapers.instagram_scraper import InstagramScraper
from transcription.transcriber import VideoTranscriber
# Removed ContentAnalyzer - using simplified RAG approach
from knowledge_base.rag_system import RAGKnowledgeBase
from coaches.ai_coach import CoachManager

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize system components
db = DatabaseManager()
rag_system = RAGKnowledgeBase(os.getenv('OPENAI_API_KEY'), db)
coach_manager = CoachManager(os.getenv('OPENAI_API_KEY'), db, rag_system)

@app.route('/')
def index():
    """Dashboard - show available coaches and system status"""
    try:
        coaches = coach_manager.get_available_coaches()
        creators = db.get_creators()

        dashboard_data = {
            "total_creators": len(creators),
            "available_coaches": len(coaches),
            "coaches": coaches
        }

        return render_template('dashboard.html', data=dashboard_data)

    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", 'error')
        return render_template('dashboard.html', data={})

@app.route('/scrape')
def scrape_page():
    """Content scraping interface"""
    return render_template('scrape.html')

@app.route('/api/scrape', methods=['POST'])
def scrape_creator():
    """API endpoint to scrape creator content"""
    try:
        data = request.get_json()
        username = data.get('username', '').replace('@', '')
        max_posts = int(data.get('max_posts', 50))

        if not username:
            return jsonify({"error": "Username is required"}), 400

        # Initialize scraper
        scraper = InstagramScraper(os.getenv('APIFY_API_TOKEN'))

        # Scrape content
        scrape_result = scraper.scrape_profile(username, max_posts)

        # Save creator to database (handle existing creators)
        creators = db.get_creators()
        existing_creator = next((c for c in creators if c['username'] == username), None)

        if existing_creator:
            creator_id = existing_creator['id']
        else:
            creator_id = db.add_creator(
                username=username,
                platform="instagram",
                display_name=scrape_result['profile_data'].get('display_name'),
                bio=scrape_result['profile_data'].get('bio')
            )

        # Save posts to database
        posts_saved = 0
        for post in scrape_result['posts']:
            try:
                db.add_post(creator_id, post)
                posts_saved += 1
            except Exception as e:
                print(f"Error saving post {post.get('post_id')}: {e}")

        return jsonify({
            "success": True,
            "creator_id": creator_id,
            "username": username,
            "posts_scraped": len(scrape_result['posts']),
            "posts_saved": posts_saved,
            "next_step": f"/process/{creator_id}"
        })

    except Exception as e:
        return jsonify({"error": f"Scraping failed: {str(e)}"}), 500

@app.route('/process/<int:creator_id>')
def process_creator(creator_id):
    """Process creator content - transcribe and analyze"""
    return render_template('process.html', creator_id=creator_id)

@app.route('/api/process/<int:creator_id>', methods=['POST'])
def process_creator_content(creator_id):
    """API endpoint to process creator content"""
    try:
        # Get creator posts
        posts = db.get_creator_posts(creator_id)
        if not posts:
            return jsonify({"error": "No posts found for creator"}), 404

        results = {
            "creator_id": creator_id,
            "total_posts": len(posts),
            "transcription_results": {},
            "analysis_results": {},
            "coach_creation_results": {}
        }

        # Step 1: Transcribe video content
        print("Starting transcription...")
        transcriber = VideoTranscriber(os.getenv('OPENAI_API_KEY'))

        video_posts = [post for post in posts if post['post_type'] == 'video' and post['media_url']]
        if video_posts:
            transcription_results = transcriber.transcribe_post_batch(video_posts)

            # Update posts with transcripts
            for result in transcription_results['success']:
                # Update database with transcript
                # This would need a method in DatabaseManager to update transcripts
                pass

            results["transcription_results"] = {
                "videos_processed": len(video_posts),
                "successful": len(transcription_results['success']),
                "failed": len(transcription_results['failed'])
            }

        # Step 2: Create simplified coach profile (no analysis needed)
        print("Creating simplified coach profile...")

        # Get creator info for profile
        creators = db.get_creators()
        creator = next((c for c in creators if c['id'] == creator_id), None)

        # Create minimal coach profile - RAG system will handle the intelligence
        coach_profile = {
            "username": creator['username'] if creator else f"creator_{creator_id}",
            "platform": "instagram",
            "content_types": ["video", "image"],
            "total_posts": len(posts),
            "transcribed_posts": len([p for p in posts if p.get('transcript')])
        }

        # Save simplified profile
        db.save_coach_profile(creator_id, coach_profile)

        results["analysis_results"] = {
            "profile_created": True,
            "total_posts": coach_profile["total_posts"],
            "transcribed_posts": coach_profile["transcribed_posts"]
        }

        # Step 3: Create knowledge base
        print("Creating knowledge base...")
        kb_result = rag_system.create_knowledge_base(creator_id, posts, coach_profile)

        results["coach_creation_results"] = {
            "knowledge_chunks": kb_result.get('total_chunks', 0),
            "coach_ready": True
        }

        return jsonify({
            "success": True,
            "results": results,
            "next_step": f"/coach/{creator_id}"
        })

    except Exception as e:
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500

@app.route('/coaches')
def coaches_list():
    """List all available coaches"""
    try:
        coaches = coach_manager.get_available_coaches()
        return render_template('coaches.html', coaches=coaches)

    except Exception as e:
        flash(f"Error loading coaches: {str(e)}", 'error')
        return render_template('coaches.html', coaches=[])

@app.route('/coach/<int:creator_id>')
def coach_interface(creator_id):
    """Chat interface for a specific coach"""
    try:
        coach = coach_manager.load_coach(creator_id)
        if not coach:
            flash(f"Coach not available for creator {creator_id}", 'error')
            return redirect(url_for('coaches_list'))

        coach_info = coach.get_coach_info()
        return render_template('coach_chat.html', coach_info=coach_info, creator_id=creator_id)

    except Exception as e:
        flash(f"Error loading coach: {str(e)}", 'error')
        return redirect(url_for('coaches_list'))

@app.route('/api/ask/<int:creator_id>', methods=['POST'])
def ask_coach(creator_id):
    """API endpoint to ask coach a question"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()

        if not question:
            return jsonify({"error": "Question is required"}), 400

        # Ask the coach
        response = coach_manager.ask_coach_by_id(creator_id, question)

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": f"Failed to get response: {str(e)}"}), 500

@app.route('/api/coach/<int:creator_id>/info')
def get_coach_info(creator_id):
    """Get coach information"""
    try:
        coach = coach_manager.load_coach(creator_id)
        if not coach:
            return jsonify({"error": "Coach not found"}), 404

        return jsonify(coach.get_coach_info())

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/coaches')
def api_coaches():
    """API endpoint to get all coaches"""
    try:
        coaches = coach_manager.get_available_coaches()
        return jsonify({"coaches": coaches})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/posts')
def posts_management():
    """Posts management interface"""
    try:
        creators = db.get_creators()
        # Add post count for each creator
        for creator in creators:
            posts = db.get_creator_posts(creator['id'])
            creator['post_count'] = len(posts)

        return render_template('posts.html', creators=creators)

    except Exception as e:
        flash(f"Error loading posts interface: {str(e)}", 'error')
        return render_template('posts.html', creators=[])

@app.route('/api/posts/<int:creator_id>')
def get_creator_posts_api(creator_id):
    """API endpoint to get posts for a creator"""
    try:
        posts = db.get_creator_posts(creator_id)

        # Add transcription status and other metadata
        for post in posts:
            post['has_transcript'] = bool(post.get('transcript'))
            post['needs_transcription'] = (post['post_type'] == 'video' and not post.get('transcript'))

        return jsonify({
            "success": True,
            "posts": posts,
            "total": len(posts)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/transcribe/<int:creator_id>', methods=['POST'])
def transcribe_creator_videos(creator_id):
    """API endpoint to transcribe videos for a creator"""
    try:
        data = request.get_json() or {}
        post_ids = data.get('post_ids', [])  # If empty, transcribe all

        posts = db.get_creator_posts(creator_id)

        # Filter to video posts that need transcription
        video_posts = []
        for post in posts:
            if post['post_type'] == 'video' and not post.get('transcript'):
                if not post_ids or post['post_id'] in post_ids:
                    video_posts.append(post)

        if not video_posts:
            return jsonify({
                "success": True,
                "message": "No videos need transcription",
                "transcribed": 0
            })

        # Initialize transcriber
        transcriber = VideoTranscriber(os.getenv('OPENAI_API_KEY'))

        # Transcribe videos
        results = transcriber.transcribe_post_batch(video_posts)

        # Update database with transcripts
        transcribed_count = 0
        for result in results['success']:
            # Update the post with transcript
            if db.update_post_transcript(result['post_id'], result['transcript']):
                transcribed_count += 1

        return jsonify({
            "success": True,
            "transcribed": transcribed_count,
            "failed": len(results['failed']),
            "total_processed": len(video_posts)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/update-coach/<int:creator_id>', methods=['POST'])
def update_coach_knowledge(creator_id):
    """API endpoint to update coach knowledge base"""
    try:
        # Get all posts for this creator
        posts = db.get_creator_posts(creator_id)

        # Filter out mock posts
        real_posts = [post for post in posts if not post['post_id'].startswith('mock_')]

        if not real_posts:
            return jsonify({"error": "No real posts found"}), 400

        # Get creator info
        creators = db.get_creators()
        creator = next((c for c in creators if c['id'] == creator_id), None)
        if not creator:
            return jsonify({"error": "Creator not found"}), 404

        # Create simplified coach profile (no analysis needed)
        coach_profile = {
            "username": creator['username'],
            "platform": creator['platform'],
            "content_types": ["video", "image"],
            "total_posts": len(real_posts),
            "transcribed_posts": len([p for p in real_posts if p.get('transcript')])
        }

        # Save updated coach profile
        db.save_coach_profile(creator_id, coach_profile)

        # Rebuild knowledge base
        kb_result = rag_system.create_knowledge_base(creator_id, real_posts, coach_profile)

        return jsonify({
            "success": True,
            "posts_analyzed": len(real_posts),
            "transcribed_posts": coach_profile["transcribed_posts"],
            "knowledge_chunks": kb_result.get('total_chunks', 0)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/posts/<post_id>/delete', methods=['DELETE'])
def delete_post(post_id):
    """API endpoint to delete a specific post"""
    try:
        success = db.delete_post(post_id)

        if success:
            return jsonify({
                "success": True,
                "message": f"Post {post_id} deleted successfully"
            })
        else:
            return jsonify({
                "success": False,
                "message": f"Post {post_id} not found or could not be deleted"
            }), 404

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/posts/bulk-delete', methods=['DELETE'])
def bulk_delete_posts():
    """API endpoint to delete multiple posts"""
    try:
        data = request.get_json()
        post_ids = data.get('post_ids', [])

        if not post_ids:
            return jsonify({
                "success": False,
                "message": "No post IDs provided"
            }), 400

        deleted_count = 0
        failed_posts = []

        for post_id in post_ids:
            success = db.delete_post(post_id)
            if success:
                deleted_count += 1
            else:
                failed_posts.append(post_id)

        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "total_requested": len(post_ids),
            "failed_posts": failed_posts,
            "message": f"Successfully deleted {deleted_count} out of {len(post_ids)} posts"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Create database tables on startup
    db.init_database()

    # Run in debug mode for development
    app.run(debug=True, host='0.0.0.0', port=5001)