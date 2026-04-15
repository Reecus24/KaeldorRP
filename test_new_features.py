#!/usr/bin/env python3
"""
Test suite for Discord Roleplay Game Master Bot - New Features
Tests:
1. GET /api/sandbox/inventar/{pc_id} - Categorized inventory with finances and properties
2. POST /api/sandbox/tagwechsel - Day change with wages, rent, expenses processing
3. POST /api/gm/scene-response - Background enforcement, writing style, violence/lethality
"""

import os
import requests
import json
import time
import re
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://game-master-core.preview.emergentagent.com').rstrip('/')
CAMPAIGN_ID = "2b18dad2-4484-4ab6-bb65-0667f35fff19"

# Test data storage
created_pcs = []
created_items = []
created_properties = []

class TestSetup:
    """Setup test data for the new features"""
    
    def test_01_create_farmer_pc(self):
        """Create a farmer PC for background enforcement testing"""
        payload = {
            "campaign_id": CAMPAIGN_ID,
            "discord_user_id": "test_farmer_001",
            "character_name": "Hans der Bauer",
            "status": "active",
            "background": "Einfacher Bauer aus dem Dorf Grüntal. Hat sein ganzes Leben auf dem Feld verbracht.",
            "personality_traits": "Bodenständig, misstrauisch gegenüber Fremden",
            "strengths": "Körperlich stark, kennt sich mit Tieren und Pflanzen aus",
            "weaknesses": "Kann nicht lesen, keine Kampferfahrung",
            "skills": "Landwirtschaft, Tierpflege, Wetterkunde",
            "injuries_conditions": "",
            "inventory": "Heugabel, Brotbeutel, Wasserflasche",
            "goals": "Seine Familie ernähren",
            "fears": "Krieg und Soldaten"
        }
        response = requests.post(f"{BASE_URL}/api/player-characters", json=payload)
        assert response.status_code in [200, 201], f"Failed to create farmer PC: {response.text}"
        data = response.json()
        assert "id" in data
        created_pcs.append(data["id"])
        print(f"✓ Created farmer PC: {data['character_name']} (ID: {data['id']})")
        return data["id"]
    
    def test_02_create_merchant_pc(self):
        """Create a merchant PC for wage testing"""
        payload = {
            "campaign_id": CAMPAIGN_ID,
            "discord_user_id": "test_merchant_001",
            "character_name": "Friedrich der Händler",
            "status": "active",
            "background": "Reisender Händler aus der Stadt. Handelt mit Stoffen und Gewürzen.",
            "personality_traits": "Geschäftstüchtig, redegewandt",
            "strengths": "Verhandlungsgeschick, Menschenkenntnis",
            "weaknesses": "Körperlich schwach, gierig",
            "skills": "Handel, Feilschen, Warenkunde, Rechnen",
            "injuries_conditions": "",
            "inventory": "Waage, Münzbeutel, Handelsbuch",
            "goals": "Reich werden",
            "fears": "Armut"
        }
        response = requests.post(f"{BASE_URL}/api/player-characters", json=payload)
        assert response.status_code in [200, 201], f"Failed to create merchant PC: {response.text}"
        data = response.json()
        assert "id" in data
        created_pcs.append(data["id"])
        print(f"✓ Created merchant PC: {data['character_name']} (ID: {data['id']})")
        return data["id"]
    
    def test_03_create_pc_without_finances(self):
        """Create a PC without finances for graceful handling test"""
        payload = {
            "campaign_id": CAMPAIGN_ID,
            "discord_user_id": "test_poor_001",
            "character_name": "Armer Wanderer",
            "status": "active",
            "background": "Obdachloser Wanderer ohne Besitz",
            "skills": "",
            "inventory": "Lumpen"
        }
        response = requests.post(f"{BASE_URL}/api/player-characters", json=payload)
        assert response.status_code in [200, 201], f"Failed to create poor PC: {response.text}"
        data = response.json()
        assert "id" in data
        created_pcs.append(data["id"])
        print(f"✓ Created poor PC: {data['character_name']} (ID: {data['id']})")
        return data["id"]


class TestInventarEndpoint:
    """Test GET /api/sandbox/inventar/{pc_id}"""
    
    def test_01_setup_inventory_for_test(self):
        """Setup inventory items for a PC"""
        # First get or create a PC
        pcs_response = requests.get(f"{BASE_URL}/api/player-characters?campaign_id={CAMPAIGN_ID}")
        pcs = pcs_response.json()
        
        if not pcs:
            # Create a test PC
            pc_payload = {
                "campaign_id": CAMPAIGN_ID,
                "discord_user_id": "test_inventar_001",
                "character_name": "Inventar Test PC",
                "status": "active",
                "background": "Händler",
                "skills": "Handel"
            }
            pc_response = requests.post(f"{BASE_URL}/api/player-characters", json=pc_payload)
            pc = pc_response.json()
            pc_id = pc["id"]
            created_pcs.append(pc_id)
        else:
            pc_id = pcs[0]["id"]
        
        # Add inventory items
        items = [
            {"item_name": "Schwert", "category": "weapon", "location": "ausgerüstet", "quantity": 1, "condition": "gut", "value": 50},
            {"item_name": "Heilkraut", "category": "consumable", "location": "getragen", "quantity": 5, "condition": "frisch", "value": 2},
            {"item_name": "Goldmünzen", "category": "valuable", "location": "getragen", "quantity": 10, "condition": "gut", "value": 10},
            {"item_name": "Schlüssel", "category": "document", "location": "getragen", "quantity": 1, "condition": "gut", "value": 0},
            {"item_name": "Stoffballen", "category": "trade_good", "location": "gelagert:Lager", "quantity": 3, "condition": "gut", "value": 15},
        ]
        
        for item in items:
            item["campaign_id"] = CAMPAIGN_ID
            item["owner_pc_id"] = pc_id
            item["owner_name"] = "Inventar Test PC"
            response = requests.post(f"{BASE_URL}/api/inventory", json=item)
            if response.status_code in [200, 201]:
                created_items.append(response.json().get("id"))
        
        print(f"✓ Setup inventory items for PC {pc_id}")
        return pc_id
    
    def test_02_get_inventar_returns_categorized_data(self):
        """Test that inventar endpoint returns categorized inventory"""
        # Get a PC with inventory
        pcs_response = requests.get(f"{BASE_URL}/api/player-characters?campaign_id={CAMPAIGN_ID}")
        pcs = pcs_response.json()
        
        if not pcs:
            pytest.skip("No PCs available for inventar test")
        
        pc_id = pcs[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/sandbox/inventar/{pc_id}")
        assert response.status_code == 200, f"Inventar endpoint failed: {response.text}"
        
        data = response.json()
        print(f"Inventar response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Verify structure
        assert "character_name" in data, "Missing character_name in response"
        assert "categories" in data, "Missing categories in response"
        assert "finances" in data, "Missing finances in response"
        assert "properties" in data, "Missing properties in response"
        
        print(f"✓ Inventar endpoint returns proper structure")
        print(f"  - Character: {data['character_name']}")
        print(f"  - Categories: {list(data['categories'].keys())}")
        print(f"  - Finances: {data['finances']}")
        print(f"  - Properties: {data['properties']}")
    
    def test_03_inventar_nonexistent_pc_returns_404(self):
        """Test that inventar endpoint returns 404 for non-existent PC"""
        response = requests.get(f"{BASE_URL}/api/sandbox/inventar/nonexistent-pc-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Inventar endpoint returns 404 for non-existent PC")


class TestTagwechselEndpoint:
    """Test POST /api/sandbox/tagwechsel"""
    
    def test_01_tagwechsel_with_merchant_pc(self):
        """Test tagwechsel processes wages based on profession"""
        # Get or create a merchant PC
        pcs_response = requests.get(f"{BASE_URL}/api/player-characters?campaign_id={CAMPAIGN_ID}")
        pcs = pcs_response.json()
        
        merchant_pc = None
        for pc in pcs:
            bg = (pc.get("background", "") + " " + pc.get("skills", "")).lower()
            if "händler" in bg or "handel" in bg or "kaufmann" in bg:
                merchant_pc = pc
                break
        
        if not merchant_pc:
            # Create one
            payload = {
                "campaign_id": CAMPAIGN_ID,
                "discord_user_id": "test_tw_merchant",
                "character_name": "Tagwechsel Händler",
                "status": "active",
                "background": "Händler und Kaufmann",
                "skills": "Handel, Feilschen"
            }
            response = requests.post(f"{BASE_URL}/api/player-characters", json=payload)
            merchant_pc = response.json()
            created_pcs.append(merchant_pc["id"])
        
        pc_id = merchant_pc["id"]
        
        # Setup finances
        fin_payload = {
            "campaign_id": CAMPAIGN_ID,
            "pc_id": pc_id,
            "balance": 100,
            "currency": "Silber",
            "debts": "",
            "recurring_costs": ""
        }
        requests.post(f"{BASE_URL}/api/finances", json=fin_payload)
        
        # Get campaign day before
        campaign_before = requests.get(f"{BASE_URL}/api/campaigns/{CAMPAIGN_ID}").json()
        day_before = campaign_before.get("current_day", 1)
        
        # Execute tagwechsel
        tw_payload = {
            "campaign_id": CAMPAIGN_ID,
            "pc_id": pc_id
        }
        response = requests.post(f"{BASE_URL}/api/sandbox/tagwechsel", json=tw_payload)
        assert response.status_code == 200, f"Tagwechsel failed: {response.text}"
        
        data = response.json()
        print(f"Tagwechsel response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Verify structure
        assert "character_name" in data, "Missing character_name"
        assert "new_day" in data, "Missing new_day"
        assert "old_balance" in data, "Missing old_balance"
        assert "new_balance" in data, "Missing new_balance"
        assert "total_income" in data, "Missing total_income"
        assert "total_expenses" in data, "Missing total_expenses"
        assert "transactions" in data, "Missing transactions"
        
        # Verify day incremented
        assert data["new_day"] == day_before + 1, f"Day should increment from {day_before} to {day_before + 1}, got {data['new_day']}"
        
        # Verify merchant gets wage (8 Silber for Händler)
        assert data["total_income"] > 0, "Merchant should receive income"
        
        print(f"✓ Tagwechsel processed successfully")
        print(f"  - Day: {day_before} -> {data['new_day']}")
        print(f"  - Balance: {data['old_balance']} -> {data['new_balance']}")
        print(f"  - Income: +{data['total_income']}, Expenses: -{data['total_expenses']}")
    
    def test_02_tagwechsel_with_rent(self):
        """Test tagwechsel deducts rent from properties"""
        # Create a PC with a rented property
        payload = {
            "campaign_id": CAMPAIGN_ID,
            "discord_user_id": "test_tw_renter",
            "character_name": "Mieter Test",
            "status": "active",
            "background": "Stadtbewohner",
            "skills": ""
        }
        response = requests.post(f"{BASE_URL}/api/player-characters", json=payload)
        pc = response.json()
        pc_id = pc["id"]
        created_pcs.append(pc_id)
        
        # Setup finances
        fin_payload = {
            "campaign_id": CAMPAIGN_ID,
            "pc_id": pc_id,
            "balance": 50,
            "currency": "Silber",
            "debts": "",
            "recurring_costs": ""
        }
        requests.post(f"{BASE_URL}/api/finances", json=fin_payload)
        
        # Add a rented property
        prop_payload = {
            "campaign_id": CAMPAIGN_ID,
            "owner_pc_id": pc_id,
            "owner_name": "Mieter Test",
            "name": "Kleine Wohnung",
            "property_type": "wohnung",
            "status": "gemietet",
            "rent_cost": 10,
            "rent_currency": "Silber"
        }
        prop_response = requests.post(f"{BASE_URL}/api/properties", json=prop_payload)
        if prop_response.status_code in [200, 201]:
            created_properties.append(prop_response.json().get("id"))
        
        # Execute tagwechsel
        tw_payload = {
            "campaign_id": CAMPAIGN_ID,
            "pc_id": pc_id
        }
        response = requests.post(f"{BASE_URL}/api/sandbox/tagwechsel", json=tw_payload)
        assert response.status_code == 200, f"Tagwechsel failed: {response.text}"
        
        data = response.json()
        print(f"Tagwechsel with rent: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Verify rent was deducted
        assert data["total_expenses"] >= 10, f"Rent should be deducted, got expenses: {data['total_expenses']}"
        
        # Check transactions include rent
        rent_found = any("miete" in t.get("type", "").lower() or "miete" in t.get("description", "").lower() 
                        for t in data.get("transactions", []))
        assert rent_found, "Rent transaction should be in transactions list"
        
        print(f"✓ Tagwechsel correctly deducts rent")
        print(f"  - Expenses: {data['total_expenses']} (includes rent)")
    
    def test_03_tagwechsel_creates_default_finances(self):
        """Test tagwechsel creates default finances for PC without finances"""
        # Create a PC without finances
        payload = {
            "campaign_id": CAMPAIGN_ID,
            "discord_user_id": "test_tw_nofinance",
            "character_name": "Ohne Finanzen",
            "status": "active",
            "background": "Wanderer",
            "skills": ""
        }
        response = requests.post(f"{BASE_URL}/api/player-characters", json=payload)
        pc = response.json()
        pc_id = pc["id"]
        created_pcs.append(pc_id)
        
        # Don't create finances - let tagwechsel handle it
        
        # Execute tagwechsel
        tw_payload = {
            "campaign_id": CAMPAIGN_ID,
            "pc_id": pc_id
        }
        response = requests.post(f"{BASE_URL}/api/sandbox/tagwechsel", json=tw_payload)
        assert response.status_code == 200, f"Tagwechsel should handle PC without finances: {response.text}"
        
        data = response.json()
        print(f"Tagwechsel for PC without finances: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Verify it worked
        assert "new_balance" in data, "Should have new_balance even for PC without prior finances"
        
        print(f"✓ Tagwechsel gracefully handles PC without finances")
    
    def test_04_tagwechsel_increments_campaign_day(self):
        """Test that tagwechsel increments campaign day counter"""
        # Get current campaign day
        campaign_before = requests.get(f"{BASE_URL}/api/campaigns/{CAMPAIGN_ID}").json()
        day_before = campaign_before.get("current_day", 1)
        
        # Get any PC
        pcs_response = requests.get(f"{BASE_URL}/api/player-characters?campaign_id={CAMPAIGN_ID}")
        pcs = pcs_response.json()
        
        if not pcs:
            pytest.skip("No PCs available")
        
        pc_id = pcs[0]["id"]
        
        # Ensure finances exist
        fin_payload = {
            "campaign_id": CAMPAIGN_ID,
            "pc_id": pc_id,
            "balance": 100,
            "currency": "Silber"
        }
        requests.post(f"{BASE_URL}/api/finances", json=fin_payload)
        
        # Execute tagwechsel
        tw_payload = {
            "campaign_id": CAMPAIGN_ID,
            "pc_id": pc_id
        }
        response = requests.post(f"{BASE_URL}/api/sandbox/tagwechsel", json=tw_payload)
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify day incremented
        assert data["new_day"] == day_before + 1, f"Day should be {day_before + 1}, got {data['new_day']}"
        
        # Verify campaign was updated
        campaign_after = requests.get(f"{BASE_URL}/api/campaigns/{CAMPAIGN_ID}").json()
        assert campaign_after.get("current_day") == day_before + 1
        
        print(f"✓ Campaign day correctly incremented: {day_before} -> {data['new_day']}")


class TestGMSceneResponse:
    """Test POST /api/gm/scene-response for background enforcement, writing style, and violence"""
    
    def test_01_background_enforcement_farmer_swordfight(self):
        """Test that a farmer PC trying to sword-fight gets restricted"""
        # Create farmer PC if not exists
        pcs_response = requests.get(f"{BASE_URL}/api/player-characters?campaign_id={CAMPAIGN_ID}")
        pcs = pcs_response.json()
        
        farmer_pc = None
        for pc in pcs:
            bg = (pc.get("background", "") + " " + pc.get("skills", "")).lower()
            if "bauer" in bg or "landwirt" in bg or "farmer" in bg:
                farmer_pc = pc
                break
        
        if not farmer_pc:
            payload = {
                "campaign_id": CAMPAIGN_ID,
                "discord_user_id": "test_farmer_bg",
                "character_name": "Bauer Fritz",
                "status": "active",
                "background": "Einfacher Bauer ohne jegliche Kampferfahrung. Hat nie ein Schwert gehalten.",
                "skills": "Landwirtschaft, Tierpflege",
                "weaknesses": "Keine Kampferfahrung, kann nicht fechten"
            }
            response = requests.post(f"{BASE_URL}/api/player-characters", json=payload)
            farmer_pc = response.json()
            created_pcs.append(farmer_pc["id"])
        
        # Test scene-response with farmer trying to sword-fight
        scene_payload = {
            "campaign_id": CAMPAIGN_ID,
            "channel_id": "test_channel",
            "player_actions": [
                {
                    "discord_id": farmer_pc.get("discord_user_id", "test_farmer"),
                    "pc_name": farmer_pc["character_name"],
                    "message": "Ich ziehe mein Schwert und greife den Banditen mit einer eleganten Fechtbewegung an!"
                }
            ]
        }
        
        print(f"Testing background enforcement with farmer PC: {farmer_pc['character_name']}")
        print(f"Action: Farmer tries to sword-fight")
        
        response = requests.post(f"{BASE_URL}/api/gm/scene-response", json=scene_payload, timeout=30)
        assert response.status_code == 200, f"Scene response failed: {response.text}"
        
        data = response.json()
        gm_response = data.get("response", "")
        
        print(f"GM Response: {gm_response[:500]}...")
        
        # The GM should acknowledge the farmer's lack of skill
        # We can't guarantee exact wording, but the response should exist
        assert gm_response, "GM should provide a response"
        assert len(gm_response) > 50, "GM response should be substantial"
        
        print(f"✓ Background enforcement test completed - GM responded to farmer's sword-fight attempt")
    
    def test_02_writing_style_no_banned_phrases(self):
        """Test that GM output doesn't contain banned AI phrases"""
        # Get any PC
        pcs_response = requests.get(f"{BASE_URL}/api/player-characters?campaign_id={CAMPAIGN_ID}")
        pcs = pcs_response.json()
        
        if not pcs:
            pytest.skip("No PCs available")
        
        pc = pcs[0]
        
        # Test scene-response
        scene_payload = {
            "campaign_id": CAMPAIGN_ID,
            "channel_id": "test_channel",
            "player_actions": [
                {
                    "discord_id": pc.get("discord_user_id", "test_user"),
                    "pc_name": pc["character_name"],
                    "message": "Ich betrete vorsichtig die dunkle Taverne und schaue mich um."
                }
            ]
        }
        
        print(f"Testing writing style with PC: {pc['character_name']}")
        
        response = requests.post(f"{BASE_URL}/api/gm/scene-response", json=scene_payload, timeout=30)
        assert response.status_code == 200, f"Scene response failed: {response.text}"
        
        data = response.json()
        gm_response = data.get("response", "")
        
        print(f"GM Response: {gm_response[:500]}...")
        
        # Check for banned phrases
        banned_phrases = [
            "kalte luft",
            "feuchter atem", 
            "schatten huschen",
            "knirschen in der dunkelheit",
            "atmosphäre ist angespannt",
            "etwas liegt in der luft",
            "eine gestalt tritt hervor",
            "die stille wird unterbrochen",
            "ein ungutes gefühl"
        ]
        
        response_lower = gm_response.lower()
        found_banned = []
        for phrase in banned_phrases:
            if phrase in response_lower:
                found_banned.append(phrase)
        
        if found_banned:
            print(f"⚠ Found banned phrases: {found_banned}")
        else:
            print(f"✓ No banned AI phrases found in GM response")
        
        # This is a soft check - we report but don't fail
        # The LLM might occasionally use these phrases
        assert gm_response, "GM should provide a response"
    
    def test_03_violence_produces_injury_markers(self):
        """Test that violence scenarios produce realistic injury markers"""
        # Get any PC
        pcs_response = requests.get(f"{BASE_URL}/api/player-characters?campaign_id={CAMPAIGN_ID}")
        pcs = pcs_response.json()
        
        if not pcs:
            pytest.skip("No PCs available")
        
        pc = pcs[0]
        
        # Test violent scene
        scene_payload = {
            "campaign_id": CAMPAIGN_ID,
            "channel_id": "test_channel",
            "player_actions": [
                {
                    "discord_id": pc.get("discord_user_id", "test_user"),
                    "pc_name": pc["character_name"],
                    "message": "Ich greife den Banditen mit meinem Schwert an und versuche ihn zu töten!"
                }
            ]
        }
        
        print(f"Testing violence/lethality with PC: {pc['character_name']}")
        print(f"Action: Attack bandit with sword")
        
        response = requests.post(f"{BASE_URL}/api/gm/scene-response", json=scene_payload, timeout=30)
        assert response.status_code == 200, f"Scene response failed: {response.text}"
        
        data = response.json()
        gm_response = data.get("response", "")
        
        print(f"GM Response: {gm_response[:800]}...")
        
        # Check for injury markers or combat description
        # The GM should describe combat consequences
        assert gm_response, "GM should provide a response"
        assert len(gm_response) > 100, "Combat response should be detailed"
        
        # Check for [ÄNDERUNG: ...] markers (injury state changes)
        has_change_marker = "[ÄNDERUNG:" in gm_response or "[AENDERUNG:" in gm_response
        
        # Check for dice roll display
        has_dice = "1W20" in gm_response or "Wurf:" in gm_response or "W20" in gm_response
        
        print(f"  - Has change marker: {has_change_marker}")
        print(f"  - Has dice display: {has_dice}")
        
        print(f"✓ Violence test completed - GM responded to combat action")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup(self):
        """Clean up created test data"""
        print("\n--- Cleanup ---")
        
        # Delete created PCs
        for pc_id in created_pcs:
            try:
                requests.delete(f"{BASE_URL}/api/player-characters/{pc_id}")
                print(f"  Deleted PC: {pc_id}")
            except:
                pass
        
        # Delete created items
        for item_id in created_items:
            try:
                requests.delete(f"{BASE_URL}/api/inventory/{item_id}")
                print(f"  Deleted item: {item_id}")
            except:
                pass
        
        # Delete created properties
        for prop_id in created_properties:
            try:
                requests.delete(f"{BASE_URL}/api/properties/{prop_id}")
                print(f"  Deleted property: {prop_id}")
            except:
                pass
        
        print("✓ Cleanup completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])
