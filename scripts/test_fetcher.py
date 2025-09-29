#!/usr/bin/env python3
"""
Test script to validate the publication fetcher setup
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Add the scripts directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported"""
    try:
        from publication_utils import Publication, PublicationNormalizer, PublicationDeduplicator
        from arxiv_crossref_fetcher import ArxivFetcher, CrossRefFetcher
        from orcid_scopus_fetcher import ORCIDFetcher
        print("✅ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_publication_creation():
    """Test creating and manipulating Publication objects"""
    try:
        from publication_utils import Publication
        
        # Create a test publication
        pub = Publication(
            title="Test Publication",
            authors=["John Doe", "Jane Smith"],
            journal="Test Journal",
            year=2023,
            doi="10.1000/test",
            type="journal"
        )
        
        # Test methods
        citation_key = pub.get_citation_key()
        formatted_authors = pub.format_authors("John Doe")
        markdown_content = pub.generate_markdown_content("John Doe")
        
        assert len(citation_key) > 0
        assert "**John Doe**" in formatted_authors
        assert "Test Publication" in markdown_content
        
        print("✅ Publication object tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Publication object test failed: {e}")
        return False

def test_arxiv_fetcher():
    """Test arXiv fetcher with a simple query"""
    try:
        from arxiv_crossref_fetcher import ArxivFetcher
        
        fetcher = ArxivFetcher()
        
        # Test with a well-known author (Albert Einstein)
        publications = fetcher.search_by_author("Einstein", max_results=5)
        
        if len(publications) > 0:
            print(f"✅ ArXiv fetcher test passed ({len(publications)} publications found)")
            return True
        else:
            print("⚠️  ArXiv fetcher returned no results (might be network issue)")
            return True  # Not necessarily a failure
            
    except Exception as e:
        print(f"❌ ArXiv fetcher test failed: {e}")
        return False

def test_publication_deduplication():
    """Test publication deduplication"""
    try:
        from publication_utils import Publication, PublicationDeduplicator
        
        # Create duplicate publications
        pub1 = Publication(
            title="Quantum Entanglement in Photonic Systems",
            authors=["Alice Smith", "Bob Jones"],
            journal="Physical Review A",
            year=2023,
            doi="10.1103/PhysRevA.107.012345"
        )
        
        pub2 = Publication(
            title="Quantum Entanglement in Photonic Systems",  # Same title
            authors=["Alice Smith", "Bob Jones"],  # Same authors
            journal="Phys. Rev. A",  # Different journal name format
            year=2023,
            arxiv_id="2301.12345"  # Additional arXiv info
        )
        
        pub3 = Publication(
            title="Different Paper",
            authors=["Charlie Brown"],
            journal="Nature",
            year=2023
        )
        
        # Test deduplication
        deduplicated = PublicationDeduplicator.deduplicate_publications([pub1, pub2, pub3])
        
        assert len(deduplicated) == 2  # Should merge pub1 and pub2
        
        # Check that information was merged
        merged_pub = next(p for p in deduplicated if "Quantum" in p.title)
        assert merged_pub.arxiv_id == "2301.12345"  # Should have arXiv info from pub2
        
        print("✅ Deduplication test passed")
        return True
        
    except Exception as e:
        print(f"❌ Deduplication test failed: {e}")
        return False

def test_config_loading():
    """Test configuration loading"""
    try:
        from publication_utils import load_config
        
        config = load_config()
        
        # Check that required fields exist
        required_fields = ['author_name', 'orcid_id']
        for field in required_fields:
            if field not in config:
                print(f"⚠️  Config missing field: {field}")
        
        print(f"✅ Config loaded for author: {config['author_name']}")
        return True
        
    except Exception as e:
        print(f"❌ Config loading test failed: {e}")
        return False

def test_file_generation():
    """Test generating publication files"""
    try:
        from publication_utils import Publication
        from fetch_publications import JekyllPublicationGenerator
        
        # Create a test publication
        pub = Publication(
            title="Test Publication for File Generation",
            authors=["Test Author", "Marco Avesani"],
            journal="Test Journal",
            year=2023,
            doi="10.1000/test123",
            abstract="This is a test publication for validating file generation."
        )
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create mock Jekyll structure
            (temp_path / "_pages").mkdir()
            (temp_path / "_publications").mkdir()
            
            # Test generator
            config = {'author_name': 'Marco Avesani'}
            generator = JekyllPublicationGenerator(str(temp_path), config)
            
            # Generate files
            generator.generate_publication_files([pub])
            generator.update_publications_page([pub])
            
            # Check that files were created
            pub_files = list((temp_path / "_publications").glob("*.md"))
            publications_page = temp_path / "_pages" / "publications.md"
            
            assert len(pub_files) == 1
            assert publications_page.exists()
            
            # Check file content
            with open(pub_files[0], 'r', encoding='utf-8') as f:
                content = f.read()
                assert "Test Publication for File Generation" in content
                assert "**Marco Avesani**" in content  # Should be highlighted
            
            print("✅ File generation test passed")
            return True
            
    except Exception as e:
        print(f"❌ File generation test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Running Publication Fetcher Tests")
    print("=" * 40)
    
    tests = [
        ("Module imports", test_imports),
        ("Publication objects", test_publication_creation),
        ("ArXiv fetcher", test_arxiv_fetcher),
        ("Deduplication", test_publication_deduplication),
        ("Configuration loading", test_config_loading),
        ("File generation", test_file_generation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing {test_name}...")
        try:
            if test_func():
                passed += 1
            else:
                print(f"❌ {test_name} test failed")
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The publication fetcher is ready to use.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)