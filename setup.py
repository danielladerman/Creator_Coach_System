#!/usr/bin/env python3
"""
Setup script for Creator Coach System
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"   ✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ {description} failed: {e.stderr}")
        return False

def check_python_version():
    """Check Python version compatibility"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ required")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} detected")
    return True

def setup_virtual_environment():
    """Create and activate virtual environment"""
    venv_path = Path("venv")

    if venv_path.exists():
        print("✅ Virtual environment already exists")
        return True

    print("🔧 Creating virtual environment...")
    if run_command(f"{sys.executable} -m venv venv", "Creating virtual environment"):
        print("✅ Virtual environment created")
        print("ℹ️  Activate with: source venv/bin/activate (Linux/Mac) or venv\\Scripts\\activate (Windows)")
        return True
    return False

def install_dependencies():
    """Install Python dependencies"""
    requirements_file = Path("requirements.txt")

    if not requirements_file.exists():
        print("❌ requirements.txt not found")
        return False

    # Try to use pip from virtual environment if it exists
    pip_cmd = "venv/bin/pip" if Path("venv/bin/pip").exists() else "pip"

    return run_command(f"{pip_cmd} install -r requirements.txt", "Installing Python dependencies")

def setup_environment_file():
    """Create .env file from template"""
    env_file = Path(".env")
    env_example = Path(".env.example")

    if env_file.exists():
        print("✅ .env file already exists")
        return True

    if not env_example.exists():
        print("❌ .env.example not found")
        return False

    print("🔧 Creating .env file from template...")
    try:
        with open(env_example, 'r') as src, open(env_file, 'w') as dst:
            dst.write(src.read())
        print("✅ .env file created")
        print("⚠️  Please edit .env file and add your API keys!")
        return True
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    dirs = [
        "database",
        "temp_downloads",
        "knowledge_base"
    ]

    for dir_name in dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created directory: {dir_name}")
        else:
            print(f"✅ Directory exists: {dir_name}")

    return True

def check_api_requirements():
    """Check if API keys are needed"""
    print("\n📋 API REQUIREMENTS:")
    print("   1. OpenAI API Key (for transcription and analysis)")
    print("      - Get it from: https://platform.openai.com/api-keys")
    print("   2. Apify API Token (for Instagram scraping)")
    print("      - Get it from: https://console.apify.com/account/integrations")
    print("   3. Add both keys to your .env file")
    return True

def run_basic_test():
    """Run basic system test"""
    print("\n🧪 Running basic system test...")

    try:
        # Test imports
        sys.path.append('.')
        from database.models import DatabaseManager
        db = DatabaseManager()
        print("✅ Database models working")

        # Test database initialization
        db.init_database()
        print("✅ Database initialization working")

        return True
    except Exception as e:
        print(f"❌ Basic test failed: {e}")
        return False

def main():
    """Main setup function"""
    print("🤖 Creator Coach System Setup")
    print("=" * 40)

    steps = [
        ("Checking Python version", check_python_version),
        ("Setting up virtual environment", setup_virtual_environment),
        ("Installing dependencies", install_dependencies),
        ("Creating .env file", setup_environment_file),
        ("Creating directories", create_directories),
        ("Checking API requirements", check_api_requirements),
        ("Running basic test", run_basic_test)
    ]

    failed_steps = []

    for step_name, step_func in steps:
        print(f"\n📋 {step_name}...")
        if not step_func():
            failed_steps.append(step_name)

    print("\n" + "=" * 40)

    if failed_steps:
        print("❌ Setup completed with errors:")
        for step in failed_steps:
            print(f"   - {step}")
        print("\n💡 Please fix the errors above before proceeding")
    else:
        print("🎉 Setup completed successfully!")
        print("\n📋 NEXT STEPS:")
        print("   1. Edit .env file and add your API keys")
        print("   2. Run: python main.py")
        print("   3. Or start web interface: python web_ui/app.py")
        print("\n🎯 Default test creator: @personalbrandlaunch")

if __name__ == "__main__":
    main()