#!/usr/bin/env python3
"""
Setup script for the academic publication fetcher
"""

import os
import sys
import subprocess
import yaml
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True

def install_requirements():
    """Install Python requirements"""
    requirements_file = Path(__file__).parent / "requirements.txt"
    
    if not requirements_file.exists():
        print("❌ requirements.txt not found")
        return False
    
    try:
        print("📦 Installing Python requirements...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
        ])
        print("✅ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        return False

def check_config():
    """Check and validate configuration"""
    config_file = Path(__file__).parent / "config.yml"
    
    if not config_file.exists():
        print("❌ config.yml not found")
        return False
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Check required fields
        required_fields = [
            ('author', 'name'),
            ('author', 'orcid_id'),
        ]
        
        missing_fields = []
        for field_path in required_fields:
            current = config
            for key in field_path:
                if key not in current:
                    missing_fields.append('.'.join(field_path))
                    break
                current = current[key]
        
        if missing_fields:
            print(f"❌ Missing required config fields: {', '.join(missing_fields)}")
            return False
        
        print("✅ Configuration validated")
        return True
        
    except yaml.YAMLError as e:
        print(f"❌ Invalid YAML in config.yml: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading config.yml: {e}")
        return False

def check_site_structure():
    """Check if Jekyll site structure is present"""
    script_dir = Path(__file__).parent
    site_root = script_dir.parent
    
    required_dirs = [
        site_root / "_pages",
        site_root / "_config.yml"
    ]
    
    missing_items = []
    for item in required_dirs:
        if not item.exists():
            missing_items.append(str(item.relative_to(site_root)))
    
    if missing_items:
        print(f"❌ Missing Jekyll site structure: {', '.join(missing_items)}")
        return False
    
    print("✅ Jekyll site structure found")
    return True

def test_fetchers():
    """Test if the fetchers can be imported and basic functionality works"""
    try:
        # Test imports
        from publication_utils import Publication, load_config
        from arxiv_crossref_fetcher import ArxivFetcher
        from orcid_scopus_fetcher import ORCIDFetcher
        
        print("✅ All modules imported successfully")
        
        # Test configuration loading
        config = load_config()
        print(f"✅ Configuration loaded for: {config['author_name']}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing fetchers: {e}")
        return False

def create_test_run():
    """Create a test run to verify everything works"""
    try:
        print("🧪 Running test fetch (arXiv only, limited results)...")
        
        # Change to scripts directory
        script_dir = Path(__file__).parent
        os.chdir(script_dir)
        
        # Run a limited test
        result = subprocess.run([
            sys.executable, "fetch_publications.py", 
            "--sources", "arxiv",
            "--cache-file", "test_cache.json",
            "--update-cache-only"
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ Test run successful")
            
            # Clean up test cache
            test_cache = script_dir / "test_cache.json"
            if test_cache.exists():
                test_cache.unlink()
            
            return True
        else:
            print(f"❌ Test run failed:")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Test run timed out")
        return False
    except Exception as e:
        print(f"❌ Error during test run: {e}")
        return False

def setup_github_actions():
    """Check GitHub Actions setup"""
    script_dir = Path(__file__).parent
    site_root = script_dir.parent
    workflow_file = site_root / ".github" / "workflows" / "update-publications.yml"
    
    if workflow_file.exists():
        print("✅ GitHub Actions workflow found")
        print(f"📁 Workflow file: {workflow_file.relative_to(site_root)}")
        return True
    else:
        print("⚠️  GitHub Actions workflow not found")
        print("   You can manually create it or copy from the provided template")
        return False

def print_next_steps():
    """Print next steps for the user"""
    print("\n" + "="*60)
    print("🎉 SETUP COMPLETE!")
    print("="*60)
    print("\n📋 NEXT STEPS:")
    print("\n1. 📝 Update your configuration:")
    print("   - Edit scripts/config.yml with your academic profile information")
    print("   - Make sure your ORCID ID and Google Scholar ID are correct")
    
    print("\n2. 🧪 Test the fetcher:")
    print("   cd scripts")
    print("   python fetch_publications.py --sources arxiv orcid")
    
    print("\n3. 🔄 Set up automation (optional):")
    print("   - The GitHub Actions workflow is already configured")
    print("   - It will run daily to check for new publications")
    print("   - You can also run it manually from the Actions tab")
    
    print("\n4. 🔑 Add API keys (optional, for more sources):")
    print("   - Scopus API: Add SCOPUS_API_KEY to GitHub secrets")
    print("   - Web of Science: Add WOS_API_KEY to GitHub secrets")
    
    print("\n5. 🚀 Manual usage:")
    print("   # Fetch from all default sources")
    print("   python scripts/fetch_publications.py")
    print("   ")
    print("   # Fetch from specific sources")
    print("   python scripts/fetch_publications.py --sources arxiv crossref")
    print("   ")
    print("   # Use cached data (faster)")
    print("   python scripts/fetch_publications.py --use-cache")
    
    print("\n📚 Documentation:")
    print("   - See README.md in the scripts/ directory for detailed usage")
    print("   - Configuration options are documented in config.yml")
    
    print("\n✨ Your publications will be automatically updated!")

def main():
    """Main setup function"""
    print("🔧 Academic Publication Fetcher Setup")
    print("=" * 40)
    
    all_checks_passed = True
    
    # Run all checks
    checks = [
        ("Python version", check_python_version),
        ("Requirements installation", install_requirements),
        ("Configuration", check_config),
        ("Jekyll site structure", check_site_structure),
        ("Module imports", test_fetchers),
        ("Test run", create_test_run),
        ("GitHub Actions", setup_github_actions),
    ]
    
    for check_name, check_func in checks:
        print(f"\n🔍 Checking {check_name}...")
        if not check_func():
            all_checks_passed = False
            print(f"⚠️  {check_name} check failed")
        else:
            print(f"✅ {check_name} check passed")
    
    if all_checks_passed:
        print_next_steps()
    else:
        print("\n❌ Some checks failed. Please resolve the issues above.")
        print("💡 You can run this setup script again after fixing the issues.")
        sys.exit(1)

if __name__ == "__main__":
    main()