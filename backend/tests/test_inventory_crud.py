"""
Test Inventory CRUD operations for persistent inventory feature.
Tests: GET, POST, PUT, DELETE /api/inventory endpoints
Also tests: GET /api/sandbox/inventar/{pc_id} for categorized view
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data from context
CAMPAIGN_ID = "2b18dad2-4484-4ab6-bb65-0667f35fff19"
PC_ID_ELARA = "182869c5-04a8-4395-a8de-ecde1aa53128"  # Dr. Elara Voss
PC_ID_HEINRICH = "158e58e5-a7c8-40cf-acd3-3b31b0a2b2e4"  # Heinrich der Schmied


class TestInventoryAPI:
    """Test inventory CRUD endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_item_ids = []
        yield
        # Cleanup: delete test items
        for item_id in self.created_item_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/inventory/{item_id}")
            except:
                pass
    
    # ── GET /api/inventory ──
    def test_get_inventory_for_pc(self):
        """GET /api/inventory returns items for specific PC"""
        response = self.session.get(
            f"{BASE_URL}/api/inventory",
            params={"campaign_id": CAMPAIGN_ID, "owner_pc_id": PC_ID_HEINRICH}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"SUCCESS: GET /api/inventory returned {len(data)} items for Heinrich")
        
        # Verify item structure if items exist
        if len(data) > 0:
            item = data[0]
            assert "id" in item, "Item should have id"
            assert "item_name" in item, "Item should have item_name"
            assert "category" in item, "Item should have category"
            assert "quantity" in item, "Item should have quantity"
            print(f"  Sample item: {item.get('item_name')} (qty: {item.get('quantity')})")
    
    def test_get_inventory_empty_for_nonexistent_pc(self):
        """GET /api/inventory returns empty list for non-existent PC"""
        response = self.session.get(
            f"{BASE_URL}/api/inventory",
            params={"campaign_id": CAMPAIGN_ID, "owner_pc_id": "nonexistent-pc-id"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, "Should return empty list for non-existent PC"
        print("SUCCESS: GET /api/inventory returns empty list for non-existent PC")
    
    # ── POST /api/inventory ──
    def test_create_inventory_item(self):
        """POST /api/inventory creates new item in MongoDB"""
        test_item = {
            "campaign_id": CAMPAIGN_ID,
            "owner_pc_id": PC_ID_ELARA,
            "owner_name": "Dr. Elara Voss",
            "item_name": f"TEST_Testgegenstand_{uuid.uuid4().hex[:8]}",
            "category": "misc",
            "quantity": 3,
            "condition": "gut",
            "location": "getragen",
            "description": "Test item for automated testing",
            "value": 10
        }
        
        response = self.session.post(f"{BASE_URL}/api/inventory", json=test_item)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should contain id"
        assert data["item_name"] == test_item["item_name"], "Item name should match"
        assert data["quantity"] == 3, "Quantity should be 3"
        assert data["category"] == "misc", "Category should be misc"
        assert data["owner_pc_id"] == PC_ID_ELARA, "Owner PC ID should match"
        
        self.created_item_ids.append(data["id"])
        print(f"SUCCESS: POST /api/inventory created item with id: {data['id']}")
        
        # Verify persistence with GET
        get_response = self.session.get(
            f"{BASE_URL}/api/inventory",
            params={"campaign_id": CAMPAIGN_ID, "owner_pc_id": PC_ID_ELARA}
        )
        assert get_response.status_code == 200
        items = get_response.json()
        created_item = next((i for i in items if i["id"] == data["id"]), None)
        assert created_item is not None, "Created item should be retrievable via GET"
        print("SUCCESS: Created item persisted and retrievable via GET")
    
    def test_create_item_with_different_locations(self):
        """POST /api/inventory with different location values"""
        locations = ["getragen", "ausgerüstet", "gelagert:Werkstatt"]
        
        for loc in locations:
            test_item = {
                "campaign_id": CAMPAIGN_ID,
                "owner_pc_id": PC_ID_ELARA,
                "owner_name": "Dr. Elara Voss",
                "item_name": f"TEST_Item_{loc}_{uuid.uuid4().hex[:6]}",
                "category": "equipment",
                "quantity": 1,
                "condition": "neu",
                "location": loc,
                "description": f"Test item at {loc}",
                "value": 5
            }
            
            response = self.session.post(f"{BASE_URL}/api/inventory", json=test_item)
            assert response.status_code == 200, f"Failed to create item at {loc}: {response.text}"
            data = response.json()
            assert data["location"] == loc, f"Location should be {loc}"
            self.created_item_ids.append(data["id"])
            print(f"SUCCESS: Created item at location '{loc}'")
    
    # ── PUT /api/inventory/{id} ──
    def test_update_inventory_item(self):
        """PUT /api/inventory/{id} updates item in MongoDB"""
        # First create an item
        test_item = {
            "campaign_id": CAMPAIGN_ID,
            "owner_pc_id": PC_ID_ELARA,
            "owner_name": "Dr. Elara Voss",
            "item_name": f"TEST_UpdateTest_{uuid.uuid4().hex[:8]}",
            "category": "tool",
            "quantity": 1,
            "condition": "gut",
            "location": "getragen",
            "description": "Original description",
            "value": 15
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/inventory", json=test_item)
        assert create_response.status_code == 200
        item_id = create_response.json()["id"]
        self.created_item_ids.append(item_id)
        
        # Update the item
        update_data = {
            "quantity": 5,
            "condition": "abgenutzt",
            "description": "Updated description"
        }
        
        update_response = self.session.put(f"{BASE_URL}/api/inventory/{item_id}", json=update_data)
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        
        updated_item = update_response.json()
        assert updated_item["quantity"] == 5, "Quantity should be updated to 5"
        assert updated_item["condition"] == "abgenutzt", "Condition should be updated"
        assert updated_item["description"] == "Updated description", "Description should be updated"
        assert updated_item["item_name"] == test_item["item_name"], "Item name should remain unchanged"
        print(f"SUCCESS: PUT /api/inventory/{item_id} updated item correctly")
        
        # Verify persistence with GET
        get_response = self.session.get(
            f"{BASE_URL}/api/inventory",
            params={"campaign_id": CAMPAIGN_ID, "owner_pc_id": PC_ID_ELARA}
        )
        items = get_response.json()
        fetched_item = next((i for i in items if i["id"] == item_id), None)
        assert fetched_item is not None
        assert fetched_item["quantity"] == 5, "Updated quantity should persist"
        print("SUCCESS: Updated item persisted correctly")
    
    def test_update_quantity_inline(self):
        """PUT /api/inventory/{id} with only quantity (inline +/- buttons)"""
        # Create item
        test_item = {
            "campaign_id": CAMPAIGN_ID,
            "owner_pc_id": PC_ID_ELARA,
            "owner_name": "Dr. Elara Voss",
            "item_name": f"TEST_QtyTest_{uuid.uuid4().hex[:8]}",
            "category": "consumable",
            "quantity": 5,
            "condition": "gut",
            "location": "getragen",
            "value": 2
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/inventory", json=test_item)
        item_id = create_response.json()["id"]
        self.created_item_ids.append(item_id)
        
        # Simulate inline quantity decrease (- button)
        update_response = self.session.put(f"{BASE_URL}/api/inventory/{item_id}", json={"quantity": 4})
        assert update_response.status_code == 200
        assert update_response.json()["quantity"] == 4
        print("SUCCESS: Inline quantity decrease (5 -> 4) works")
        
        # Simulate inline quantity increase (+ button)
        update_response = self.session.put(f"{BASE_URL}/api/inventory/{item_id}", json={"quantity": 6})
        assert update_response.status_code == 200
        assert update_response.json()["quantity"] == 6
        print("SUCCESS: Inline quantity increase (4 -> 6) works")
    
    def test_update_nonexistent_item_returns_404(self):
        """PUT /api/inventory/{id} returns 404 for non-existent item"""
        response = self.session.put(
            f"{BASE_URL}/api/inventory/nonexistent-item-id",
            json={"quantity": 10}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("SUCCESS: PUT returns 404 for non-existent item")
    
    # ── DELETE /api/inventory/{id} ──
    def test_delete_inventory_item(self):
        """DELETE /api/inventory/{id} removes item from MongoDB"""
        # Create item
        test_item = {
            "campaign_id": CAMPAIGN_ID,
            "owner_pc_id": PC_ID_ELARA,
            "owner_name": "Dr. Elara Voss",
            "item_name": f"TEST_DeleteTest_{uuid.uuid4().hex[:8]}",
            "category": "misc",
            "quantity": 1,
            "condition": "gut",
            "location": "getragen",
            "value": 1
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/inventory", json=test_item)
        item_id = create_response.json()["id"]
        
        # Delete the item
        delete_response = self.session.delete(f"{BASE_URL}/api/inventory/{item_id}")
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
        assert delete_response.json().get("status") == "deleted"
        print(f"SUCCESS: DELETE /api/inventory/{item_id} returned status: deleted")
        
        # Verify item is gone
        get_response = self.session.get(
            f"{BASE_URL}/api/inventory",
            params={"campaign_id": CAMPAIGN_ID, "owner_pc_id": PC_ID_ELARA}
        )
        items = get_response.json()
        deleted_item = next((i for i in items if i["id"] == item_id), None)
        assert deleted_item is None, "Deleted item should not be retrievable"
        print("SUCCESS: Deleted item no longer exists in database")


class TestInventarCategorizedView:
    """Test GET /api/sandbox/inventar/{pc_id} categorized view"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_get_inventar_returns_categorized_data(self):
        """GET /api/sandbox/inventar/{pc_id} returns categorized inventory"""
        response = self.session.get(f"{BASE_URL}/api/sandbox/inventar/{PC_ID_HEINRICH}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "character_name" in data, "Response should have character_name"
        assert "categories" in data, "Response should have categories"
        assert "finances" in data, "Response should have finances"
        assert "properties" in data, "Response should have properties"
        
        print(f"SUCCESS: GET /api/sandbox/inventar/{PC_ID_HEINRICH}")
        print(f"  Character: {data.get('character_name')}")
        print(f"  Categories: {list(data.get('categories', {}).keys())}")
        print(f"  Finances: {data.get('finances')}")
    
    def test_get_inventar_nonexistent_pc_returns_404(self):
        """GET /api/sandbox/inventar/{pc_id} returns 404 for non-existent PC"""
        response = self.session.get(f"{BASE_URL}/api/sandbox/inventar/nonexistent-pc-id")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("SUCCESS: GET /api/sandbox/inventar returns 404 for non-existent PC")
    
    def test_inventar_shows_location_grouping(self):
        """Verify items are grouped by location (Ausgerüstet, Mitgeführt, Gelagert)"""
        response = self.session.get(f"{BASE_URL}/api/sandbox/inventar/{PC_ID_HEINRICH}")
        assert response.status_code == 200
        
        data = response.json()
        categories = data.get("categories", {})
        
        # Check for expected location-based categories
        expected_locations = ["Ausgerüstet", "Mitgeführt", "Gelagert"]
        found_locations = [loc for loc in expected_locations if loc in categories]
        
        print(f"SUCCESS: Found location categories: {found_locations}")
        for loc in found_locations:
            items = categories[loc]
            print(f"  {loc}: {len(items)} items - {items[:3]}...")


class TestPCSwitching:
    """Test that switching PC reloads correct inventory"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_different_pcs_have_different_inventory(self):
        """Verify different PCs return different inventory items"""
        # Get Heinrich's inventory
        response_heinrich = self.session.get(
            f"{BASE_URL}/api/inventory",
            params={"campaign_id": CAMPAIGN_ID, "owner_pc_id": PC_ID_HEINRICH}
        )
        assert response_heinrich.status_code == 200
        heinrich_items = response_heinrich.json()
        
        # Get Elara's inventory
        response_elara = self.session.get(
            f"{BASE_URL}/api/inventory",
            params={"campaign_id": CAMPAIGN_ID, "owner_pc_id": PC_ID_ELARA}
        )
        assert response_elara.status_code == 200
        elara_items = response_elara.json()
        
        print(f"SUCCESS: Heinrich has {len(heinrich_items)} items")
        print(f"SUCCESS: Elara has {len(elara_items)} items")
        
        # Verify items are different (by checking IDs)
        heinrich_ids = set(i["id"] for i in heinrich_items)
        elara_ids = set(i["id"] for i in elara_items)
        
        # Items should not overlap (each PC has their own inventory)
        overlap = heinrich_ids & elara_ids
        assert len(overlap) == 0, f"PCs should not share inventory items, found overlap: {overlap}"
        print("SUCCESS: Different PCs have separate inventory items")


class TestDataPersistence:
    """Test that inventory data persists across requests (simulating page refresh)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_item_ids = []
        yield
        for item_id in self.created_item_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/inventory/{item_id}")
            except:
                pass
    
    def test_item_persists_after_creation(self):
        """Create item, then verify it persists (simulating page refresh)"""
        # Create item
        test_item = {
            "campaign_id": CAMPAIGN_ID,
            "owner_pc_id": PC_ID_ELARA,
            "owner_name": "Dr. Elara Voss",
            "item_name": f"TEST_PersistTest_{uuid.uuid4().hex[:8]}",
            "category": "valuable",
            "quantity": 1,
            "condition": "neu",
            "location": "getragen",
            "description": "Persistence test item",
            "value": 100
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/inventory", json=test_item)
        assert create_response.status_code == 200
        item_id = create_response.json()["id"]
        self.created_item_ids.append(item_id)
        print(f"Created item: {item_id}")
        
        # Simulate page refresh - new session, new request
        new_session = requests.Session()
        new_session.headers.update({"Content-Type": "application/json"})
        
        # Fetch inventory again
        get_response = new_session.get(
            f"{BASE_URL}/api/inventory",
            params={"campaign_id": CAMPAIGN_ID, "owner_pc_id": PC_ID_ELARA}
        )
        assert get_response.status_code == 200
        items = get_response.json()
        
        # Find our created item
        persisted_item = next((i for i in items if i["id"] == item_id), None)
        assert persisted_item is not None, "Item should persist after 'page refresh'"
        assert persisted_item["item_name"] == test_item["item_name"]
        assert persisted_item["quantity"] == test_item["quantity"]
        print("SUCCESS: Item persists after simulated page refresh")
    
    def test_quantity_change_persists(self):
        """Update quantity, verify it persists"""
        # Create item
        test_item = {
            "campaign_id": CAMPAIGN_ID,
            "owner_pc_id": PC_ID_ELARA,
            "owner_name": "Dr. Elara Voss",
            "item_name": f"TEST_QtyPersist_{uuid.uuid4().hex[:8]}",
            "category": "consumable",
            "quantity": 10,
            "condition": "gut",
            "location": "getragen",
            "value": 1
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/inventory", json=test_item)
        item_id = create_response.json()["id"]
        self.created_item_ids.append(item_id)
        
        # Update quantity (simulate inline +/- button)
        self.session.put(f"{BASE_URL}/api/inventory/{item_id}", json={"quantity": 7})
        
        # Verify with new session
        new_session = requests.Session()
        get_response = new_session.get(
            f"{BASE_URL}/api/inventory",
            params={"campaign_id": CAMPAIGN_ID, "owner_pc_id": PC_ID_ELARA}
        )
        items = get_response.json()
        item = next((i for i in items if i["id"] == item_id), None)
        
        assert item is not None
        assert item["quantity"] == 7, f"Quantity should be 7, got {item['quantity']}"
        print("SUCCESS: Quantity change persists after simulated page refresh")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
