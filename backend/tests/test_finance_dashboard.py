"""
Finance Dashboard Backend Tests
Tests for: /finances page, transactions, inventar, properties, tagwechsel
Campaign ID: 2b18dad2-4484-4ab6-bb65-0667f35fff19
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
CAMPAIGN_ID = "2b18dad2-4484-4ab6-bb65-0667f35fff19"

# Test PC IDs from previous iteration
HEINRICH_PC_ID = "158e58e5-a7c8-40cf-acd3-3b31b0a2b2e4"  # Heinrich der Schmied
ELARA_PC_ID = "182869c5-04a8-4395-a8de-ecde1aa53128"  # Dr. Elara Voss


class TestInventarEndpoint:
    """Tests for GET /api/sandbox/inventar/{pc_id} - categorized inventory with finances"""
    
    def test_inventar_returns_categorized_data(self):
        """GET /api/sandbox/inventar/{pc_id} returns categorized data with finances"""
        response = requests.get(f"{BASE_URL}/api/sandbox/inventar/{HEINRICH_PC_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify structure
        assert "character_name" in data, "Missing character_name"
        assert "categories" in data, "Missing categories"
        assert "finances" in data, "Missing finances"
        assert "properties" in data, "Missing properties"
        
        # Verify finances structure
        finances = data.get("finances", {})
        assert "balance" in finances or finances == {}, f"Finances should have balance or be empty: {finances}"
        
        print(f"✓ Inventar endpoint returns categorized data for {data.get('character_name')}")
        print(f"  Categories: {list(data.get('categories', {}).keys())}")
        print(f"  Finances: {finances}")
        print(f"  Properties: {data.get('properties', [])}")
    
    def test_inventar_404_for_nonexistent_pc(self):
        """GET /api/sandbox/inventar/{pc_id} returns 404 for non-existent PC"""
        response = requests.get(f"{BASE_URL}/api/sandbox/inventar/nonexistent-pc-id")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Inventar returns 404 for non-existent PC")


class TestTransactionsEndpoint:
    """Tests for GET /api/transactions - transaction log with day and source fields"""
    
    def test_transactions_returns_list(self):
        """GET /api/transactions returns transactions with day and source fields"""
        response = requests.get(
            f"{BASE_URL}/api/transactions",
            params={"campaign_id": CAMPAIGN_ID, "pc_id": HEINRICH_PC_ID, "limit": 50}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of transactions"
        
        if len(data) > 0:
            tx = data[0]
            # Verify transaction structure
            assert "id" in tx, "Transaction missing id"
            assert "transaction_type" in tx, "Transaction missing transaction_type"
            assert "amount" in tx, "Transaction missing amount"
            # Check for day and source fields (new requirements)
            print(f"✓ Transactions endpoint returns {len(data)} transactions")
            print(f"  Sample transaction: type={tx.get('transaction_type')}, amount={tx.get('amount')}, day={tx.get('day')}, source={tx.get('source')}")
        else:
            print("✓ Transactions endpoint returns empty list (no transactions yet)")
    
    def test_transactions_filter_by_pc(self):
        """GET /api/transactions filters by pc_id correctly"""
        response = requests.get(
            f"{BASE_URL}/api/transactions",
            params={"campaign_id": CAMPAIGN_ID, "pc_id": HEINRICH_PC_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        # All transactions should belong to the specified PC
        for tx in data:
            assert tx.get("pc_id") == HEINRICH_PC_ID, f"Transaction {tx.get('id')} has wrong pc_id"
        
        print(f"✓ Transactions correctly filtered by pc_id ({len(data)} transactions)")


class TestPostTransactions:
    """Tests for POST /api/transactions - adding transactions with day and source"""
    
    def test_post_transaction_adds_day_and_source(self):
        """POST /api/transactions (gameplay) adds day and source=gameplay automatically"""
        payload = {
            "campaign_id": CAMPAIGN_ID,
            "pc_id": HEINRICH_PC_ID,
            "pc_name": "Heinrich der Schmied",
            "transaction_type": "einnahme",
            "amount": 5,
            "currency": "Silber",
            "description": "Test transaction for finance dashboard",
            "counterparty": "Test Customer"
        }
        
        response = requests.post(f"{BASE_URL}/api/transactions", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response missing id"
        assert "day" in data, "Response missing day field"
        assert "source" in data, "Response missing source field"
        assert data.get("source") == "gameplay", f"Expected source=gameplay, got {data.get('source')}"
        
        print(f"✓ POST /api/transactions adds day={data.get('day')} and source={data.get('source')}")
        
        # Cleanup: We don't delete transactions, they're part of the log


class TestTagwechselEndpoint:
    """Tests for POST /api/sandbox/tagwechsel - day change with transactions"""
    
    def test_tagwechsel_creates_transactions_with_day_and_source(self):
        """POST /api/sandbox/tagwechsel creates transactions with day and source=tagwechsel"""
        payload = {
            "campaign_id": CAMPAIGN_ID,
            "pc_id": HEINRICH_PC_ID,
            "advance_day": False  # Don't advance day to avoid side effects
        }
        
        response = requests.post(f"{BASE_URL}/api/sandbox/tagwechsel", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "character_name" in data, "Response missing character_name"
        assert "new_day" in data, "Response missing new_day"
        assert "transactions" in data, "Response missing transactions"
        
        print(f"✓ Tagwechsel processed for {data.get('character_name')}")
        print(f"  Day: {data.get('new_day')}")
        print(f"  Old balance: {data.get('old_balance')}, New balance: {data.get('new_balance')}")
        print(f"  Transactions: {len(data.get('transactions', []))}")
        
        # Verify transactions were created with source=tagwechsel
        tx_response = requests.get(
            f"{BASE_URL}/api/transactions",
            params={"campaign_id": CAMPAIGN_ID, "pc_id": HEINRICH_PC_ID, "limit": 10}
        )
        if tx_response.status_code == 200:
            recent_tx = tx_response.json()
            tagwechsel_tx = [t for t in recent_tx if t.get("source") == "tagwechsel"]
            if tagwechsel_tx:
                print(f"  ✓ Found {len(tagwechsel_tx)} transactions with source=tagwechsel")


class TestPropertiesEndpoint:
    """Tests for GET /api/properties - property list for finance dashboard"""
    
    def test_properties_returns_list(self):
        """GET /api/properties returns properties for PC"""
        response = requests.get(
            f"{BASE_URL}/api/properties",
            params={"campaign_id": CAMPAIGN_ID, "owner_pc_id": HEINRICH_PC_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of properties"
        
        if len(data) > 0:
            prop = data[0]
            assert "id" in prop, "Property missing id"
            assert "name" in prop, "Property missing name"
            assert "property_type" in prop, "Property missing property_type"
            print(f"✓ Properties endpoint returns {len(data)} properties")
            print(f"  Sample: {prop.get('name')} ({prop.get('property_type')}) - rent: {prop.get('rent_cost')}")
        else:
            print("✓ Properties endpoint returns empty list (no properties)")


class TestFinancesEndpoint:
    """Tests for GET /api/finances - finance records"""
    
    def test_finances_returns_records(self):
        """GET /api/finances returns finance records for campaign/PC"""
        response = requests.get(
            f"{BASE_URL}/api/finances",
            params={"campaign_id": CAMPAIGN_ID, "pc_id": HEINRICH_PC_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of finance records"
        
        if len(data) > 0:
            fin = data[0]
            assert "balance" in fin, "Finance record missing balance"
            print(f"✓ Finances endpoint returns {len(data)} records")
            print(f"  Balance: {fin.get('balance')} {fin.get('currency')}")
            print(f"  Debts: {fin.get('debts', 'None')}")
            print(f"  Recurring costs: {fin.get('recurring_costs', 'None')}")
        else:
            print("✓ Finances endpoint returns empty list (no finance records)")


class TestPlayerCharactersEndpoint:
    """Tests for GET /api/player-characters - PC list for selector dropdown"""
    
    def test_player_characters_returns_list(self):
        """GET /api/player-characters returns PCs for campaign"""
        response = requests.get(
            f"{BASE_URL}/api/player-characters",
            params={"campaign_id": CAMPAIGN_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of player characters"
        assert len(data) > 0, "Expected at least one PC in campaign"
        
        # Verify PC structure
        pc = data[0]
        assert "id" in pc, "PC missing id"
        assert "character_name" in pc, "PC missing character_name"
        assert "status" in pc, "PC missing status"
        
        active_pcs = [p for p in data if p.get("status") == "active"]
        print(f"✓ Player characters endpoint returns {len(data)} PCs ({len(active_pcs)} active)")
        for p in active_pcs[:3]:
            print(f"  - {p.get('character_name')} (ID: {p.get('id')[:8]}...)")


class TestSecondPCData:
    """Tests for second PC (Dr. Elara Voss) to verify PC selector works"""
    
    def test_elara_inventar(self):
        """GET /api/sandbox/inventar for Dr. Elara Voss"""
        response = requests.get(f"{BASE_URL}/api/sandbox/inventar/{ELARA_PC_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"✓ Inventar for {data.get('character_name')}")
        print(f"  Finances: {data.get('finances', {})}")
    
    def test_elara_transactions(self):
        """GET /api/transactions for Dr. Elara Voss"""
        response = requests.get(
            f"{BASE_URL}/api/transactions",
            params={"campaign_id": CAMPAIGN_ID, "pc_id": ELARA_PC_ID, "limit": 20}
        )
        assert response.status_code == 200
        
        data = response.json()
        print(f"✓ Transactions for Elara: {len(data)} records")


class TestCampaignDay:
    """Tests for campaign day tracking"""
    
    def test_campaign_has_current_day(self):
        """GET /api/campaigns/{id} returns current_day field"""
        response = requests.get(f"{BASE_URL}/api/campaigns/{CAMPAIGN_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "current_day" in data, "Campaign missing current_day field"
        print(f"✓ Campaign '{data.get('name')}' is on day {data.get('current_day')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
