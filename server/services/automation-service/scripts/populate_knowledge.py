"""
Populate Qdrant with Drone Business Knowledge
==============================================
Seeds the Qdrant collection with business context for testing.
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from sentence_transformers import SentenceTransformer
import uuid

# User data
USER_ID = "2a63a957-d229-483e-8b40-675e8a9f255a"

# Drone products from the data structure provided
DRONE_PRODUCTS = [
    {
        "title": "SkyVision Pro",
        "category": "product_service",
        "subtype": "product",
        "description": "Professional 4K aerial photography drone",
        "price": 385459,
        "sku": "DRN-056-8515",
        "keywords": ["professional", "aerial", "photography", "drone", "4K"],
        "capabilities": ["photography"],
        "search_text": "SkyVision Pro is a professional 4K aerial photography drone priced at ₹385,459. Perfect for professional photographers and videographers. Features high-resolution 4K camera, stable flight control, and long battery life."
    },
    {
        "title": "CargoLift 200",
        "category": "product_service",
        "subtype": "product",
        "description": "Heavy payload delivery drone",
        "price": 132518,
        "sku": "DRN-078-5873",
        "keywords": ["heavy", "payload", "delivery", "drone", "cargo"],
        "capabilities": ["delivery"],
        "search_text": "CargoLift 200 is a heavy payload delivery drone priced at ₹132,518. Designed for commercial delivery operations with capacity up to 200kg. Ideal for logistics companies and last-mile delivery."
    },
    {
        "title": "AgriFly X1",
        "category": "product_service",
        "subtype": "product",
        "description": "Agricultural monitoring and spraying drone",
        "price": 245000,
        "sku": "DRN-045-3312",
        "keywords": ["agriculture", "monitoring", "spraying", "farming", "drone"],
        "capabilities": ["monitoring", "spraying"],
        "search_text": "AgriFly X1 is an agricultural monitoring and spraying drone priced at ₹245,000. Features thermal imaging for crop health monitoring and precision spraying system. Perfect for farms and agricultural operations."
    },
    {
        "title": "NightHawk IR",
        "category": "product_service",
        "subtype": "product",
        "description": "Thermal imaging surveillance drone",
        "price": 425000,
        "sku": "DRN-089-7721",
        "keywords": ["thermal", "imaging", "surveillance", "security", "night"],
        "capabilities": ["surveillance", "thermal_imaging"],
        "search_text": "NightHawk IR is a thermal imaging surveillance drone priced at ₹425,000. Equipped with advanced thermal camera for night operations and security surveillance. Ideal for security agencies and industrial inspections."
    },
    {
        "title": "Mapping & GIS",
        "category": "product_service",
        "subtype": "service",
        "description": "Drone mapping and GIS surveying service",
        "price": 75000,
        "sku": "DRN-SRV-001",
        "keywords": ["mapping", "GIS", "surveying", "service", "aerial"],
        "capabilities": ["mapping", "surveying"],
        "search_text": "Mapping & GIS is our professional drone mapping and surveying service priced at ₹75,000 per project. We provide high-resolution aerial surveys, 3D mapping, and GIS data collection for construction and land development projects."
    }
]

# Business information
BUSINESS_INFO = [
    {
        "title": "FlyDrone Company Overview",
        "category": "company_info",
        "subtype": "about",
        "search_text": "FlyDrone is a leading drone technology company in India specializing in selling variety of drones and their customization. We serve both B2B and B2C markets with professional communication. Our industries include Technology and we operate in Enterprise segment."
    },
    {
        "title": "Customization Services",
        "category": "product_service",
        "subtype": "service",
        "search_text": "We offer comprehensive drone customization services including camera upgrades, payload modifications, flight time extensions, custom paint jobs, and specialized sensor integration. Contact us for custom quotes based on your specific requirements."
    },
    {
        "title": "Bulk Order Discounts",
        "category": "pricing",
        "subtype": "discount",
        "search_text": "We offer attractive bulk order discounts for businesses purchasing multiple drones. Orders of 5+ drones get 10% discount, 10+ drones get 15% discount, and 20+ drones get 20% discount. Enterprise packages available for large deployments."
    },
    {
        "title": "Target Customers",
        "category": "company_info",
        "subtype": "audience",
        "search_text": "Our target audience includes B2B clients such as construction companies, agricultural businesses, security agencies, logistics companies, and real estate firms. We also serve B2C customers including professional photographers, hobbyists, and small business owners."
    },
    {
        "title": "Drone Training Services",
        "category": "product_service",
        "subtype": "service",
        "search_text": "We provide comprehensive drone training services including pilot certification courses, safety training, maintenance workshops, and operational best practices. Training packages start from ₹25,000 per person."
    }
]

async def populate_qdrant():
    print("=" * 70)
    print("POPULATING QDRANT WITH DRONE BUSINESS KNOWLEDGE")
    print("=" * 70)
    
    print(f"\nUser ID: {USER_ID}")
    print("Loading embedding model...")
    
    # Load embedding model
    embedder = SentenceTransformer('all-MiniLM-L6-v2')
    print("Embedding model loaded: all-MiniLM-L6-v2 (384 dimensions)")
    
    # Connect to Qdrant
    print("\nConnecting to Qdrant...")
    client = QdrantClient(url="http://localhost:6333")
    collection_name = "business_context"
    
    # Prepare points
    print("\nPreparing data points...")
    points = []
    
    # Add products
    for idx, product in enumerate(DRONE_PRODUCTS):
        # Generate embedding
        embedding = embedder.encode(product["search_text"]).tolist()
        
        # Create point
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "user_id": USER_ID,
                "entry_id": str(uuid.uuid4()),
                "category": product["category"],
                "subtype": product["subtype"],
                "title": product["title"],
                "content": product["search_text"],
                "search_text": product["search_text"],
                "metadata": {
                    "price": product.get("price"),
                    "sku": product.get("sku"),
                    "description": product["description"],
                    "keywords": product["keywords"],
                    "capabilities": product.get("capabilities", [])
                },
                "source": "product_catalog",
                "priority_score": 5
            }
        )
        points.append(point)
        print(f"  [{idx+1}] {product['title']} - {len(product['search_text'])} chars")
    
    # Add business info
    for idx, info in enumerate(BUSINESS_INFO):
        # Generate embedding
        embedding = embedder.encode(info["search_text"]).tolist()
        
        # Create point
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "user_id": USER_ID,
                "entry_id": str(uuid.uuid4()),
                "category": info["category"],
                "subtype": info["subtype"],
                "title": info["title"],
                "content": info["search_text"],
                "search_text": info["search_text"],
                "metadata": {},
                "source": "business_info",
                "priority_score": 4
            }
        )
        points.append(point)
        print(f"  [{len(DRONE_PRODUCTS)+idx+1}] {info['title']} - {len(info['search_text'])} chars")
    
    # Upload to Qdrant
    print(f"\nUploading {len(points)} points to Qdrant...")
    try:
        client.upsert(
            collection_name=collection_name,
            points=points
        )
        print(f"[OK] Uploaded {len(points)} points successfully")
    except Exception as e:
        print(f"[ERROR] Upload failed: {e}")
        return False
    
    # Verify
    print("\nVerifying upload...")
    try:
        collection_info = client.get_collection(collection_name)
        print(f"[OK] Collection now has {collection_info.points_count} points")
    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
        return False
    
    # Test search
    print("\nTesting search...")
    try:
        test_query = "What drones do you have for agricultural surveying?"
        query_embedding = embedder.encode(test_query).tolist()
        
        results = client.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            limit=3,
            query_filter={
                "must": [
                    {
                        "key": "user_id",
                        "match": {"value": USER_ID}
                    }
                ]
            }
        )
        
        print(f"[OK] Test query: '{test_query}'")
        print(f"[OK] Found {len(results)} results:")
        for i, hit in enumerate(results, 1):
            print(f"  {i}. [{hit.score:.3f}] {hit.payload.get('title')} - {hit.payload.get('category')}")
    except Exception as e:
        print(f"[ERROR] Search test failed: {e}")
        return False
    
    client.close()
    
    print("\n" + "=" * 70)
    print("POPULATION COMPLETE")
    print("=" * 70)
    print(f"\n[SUCCESS] Populated {len(points)} knowledge entries:")
    print(f"  - Products: {len(DRONE_PRODUCTS)}")
    print(f"  - Business Info: {len(BUSINESS_INFO)}")
    print(f"\nNext step: Run pipeline test")
    print("  python test_pipeline_mock.py")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    success = asyncio.run(populate_qdrant())
    sys.exit(0 if success else 1)
