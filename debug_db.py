#!/usr/bin/env python3
from database.models import DatabaseManager

db = DatabaseManager()
creators = db.get_creators()

print("DATABASE CONTENTS:")
print("=" * 50)

for creator in creators:
    posts = db.get_creator_posts(creator['id'])
    coach_profile = db.get_coach_profile(creator['id'])

    print(f"Creator {creator['id']}: @{creator['username']}")
    print(f"  - Posts: {len(posts)}")
    print(f"  - Coach Profile: {'✅' if coach_profile else '❌'}")

    if posts:
        real_posts = [p for p in posts if not p['post_id'].startswith('mock_')]
        mock_posts = [p for p in posts if p['post_id'].startswith('mock_')]
        print(f"  - Real posts: {len(real_posts)}")
        print(f"  - Mock posts: {len(mock_posts)}")

        if real_posts:
            print(f"  - Sample real post: {real_posts[0]['post_id']}")
            caption = (real_posts[0]['caption_text'] or '')[:100]
            print(f"  - Caption preview: {caption}...")

        if mock_posts:
            print(f"  - Sample mock post: {mock_posts[0]['post_id']}")

    if coach_profile:
        print(f"  - Expertise areas: {len(coach_profile.get('expertise_areas', []))}")
        print(f"  - Analysis date: {coach_profile.get('analysis_date', 'N/A')}")

    print()