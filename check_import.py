"""Test if models import correctly"""

print("Testing models import...")

try:
    from src.models import Project, BomRow, MasterItem, Order, Config
    print("✅ Successfully imported all models!")
    print(f"   - Project: {Project}")
    print(f"   - BomRow: {BomRow}")
    print(f"   - MasterItem: {MasterItem}")
    print(f"   - Order: {Order}")
    print(f"   - Config: {Config}")
    
    # Test creating a Project
    test_project = Project(name="Test Project", description="This is a test")
    print(f"\n✅ Created test project: {test_project.name}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()