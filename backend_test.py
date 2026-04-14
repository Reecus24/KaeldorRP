import requests
import sys
import json
from datetime import datetime

class GMBotAPITester:
    def __init__(self, base_url="https://game-master-core.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_campaign_id = "b4bccb7c-6a37-49f0-bf67-5de49f28aeb0"
        self.created_ids = {}  # Track created resources for cleanup

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Response: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test GET /api/ returns welcome message"""
        success, response = self.run_test(
            "Root endpoint",
            "GET",
            "",
            200
        )
        if success and 'message' in response:
            print(f"   Message: {response['message']}")
        return success

    def test_bot_status(self):
        """Test GET /api/bot/status returns campaign/npc/event counts"""
        success, response = self.run_test(
            "Bot status",
            "GET",
            "bot/status",
            200
        )
        if success:
            print(f"   Campaigns: {response.get('campaigns', 0)}")
            print(f"   NPCs: {response.get('npcs', 0)}")
            print(f"   Events: {response.get('events', 0)}")
            if response.get('active_campaign'):
                print(f"   Active Campaign: {response['active_campaign']['name']}")
        return success

    def test_create_campaign(self):
        """Test POST /api/campaigns creates a new campaign"""
        campaign_data = {
            "name": f"Test Campaign {datetime.now().strftime('%H%M%S')}",
            "world_summary": "A test world for API testing",
            "tone": "realistic"
        }
        success, response = self.run_test(
            "Create campaign",
            "POST",
            "campaigns",
            200,
            data=campaign_data
        )
        if success and 'id' in response:
            self.created_ids['campaign'] = response['id']
            print(f"   Created campaign ID: {response['id']}")
        return success

    def test_list_campaigns(self):
        """Test GET /api/campaigns lists campaigns"""
        success, response = self.run_test(
            "List campaigns",
            "GET",
            "campaigns",
            200
        )
        if success:
            print(f"   Found {len(response)} campaigns")
        return success

    def test_get_active_campaign(self):
        """Test GET /api/campaigns/active returns active campaign"""
        success, response = self.run_test(
            "Get active campaign",
            "GET",
            "campaigns/active",
            200
        )
        if success and 'name' in response:
            print(f"   Active campaign: {response['name']}")
        return success

    def test_update_campaign(self):
        """Test PUT /api/campaigns/{id} updates a campaign"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        update_data = {
            "world_summary": "Updated world summary for testing"
        }
        success, response = self.run_test(
            "Update campaign",
            "PUT",
            f"campaigns/{campaign_id}",
            200,
            data=update_data
        )
        if success:
            print(f"   Updated campaign: {response.get('name', 'Unknown')}")
        return success

    def test_create_npc(self):
        """Test POST /api/npcs creates an NPC"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        npc_data = {
            "campaign_id": campaign_id,
            "name": f"Test NPC {datetime.now().strftime('%H%M%S')}",
            "role": "Test Character",
            "faction": "Test Faction",
            "personality_traits": "Friendly and helpful",
            "motivation": "To help with testing",
            "trust_level": 50,
            "status": "alive"
        }
        success, response = self.run_test(
            "Create NPC",
            "POST",
            "npcs",
            200,
            data=npc_data
        )
        if success and 'id' in response:
            self.created_ids['npc'] = response['id']
            print(f"   Created NPC ID: {response['id']}")
        return success

    def test_list_npcs(self):
        """Test GET /api/npcs?campaign_id= lists NPCs for a campaign"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        success, response = self.run_test(
            "List NPCs",
            "GET",
            "npcs",
            200,
            params={"campaign_id": campaign_id}
        )
        if success:
            print(f"   Found {len(response)} NPCs")
        return success

    def test_update_npc(self):
        """Test PUT /api/npcs/{id} updates an NPC"""
        npc_id = self.created_ids.get('npc')
        if not npc_id:
            print("   Skipping - no NPC created")
            return True
        
        update_data = {
            "personality_traits": "Updated personality for testing"
        }
        success, response = self.run_test(
            "Update NPC",
            "PUT",
            f"npcs/{npc_id}",
            200,
            data=update_data
        )
        return success

    def test_delete_npc(self):
        """Test DELETE /api/npcs/{id} deletes an NPC"""
        npc_id = self.created_ids.get('npc')
        if not npc_id:
            print("   Skipping - no NPC created")
            return True
        
        success, response = self.run_test(
            "Delete NPC",
            "DELETE",
            f"npcs/{npc_id}",
            200
        )
        if success:
            self.created_ids.pop('npc', None)
        return success

    def test_create_lore(self):
        """Test POST /api/lore creates lore entry"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        lore_data = {
            "campaign_id": campaign_id,
            "category": "custom",
            "title": f"Test Lore {datetime.now().strftime('%H%M%S')}",
            "content": "This is test lore content for API testing",
            "tags": ["test", "api"]
        }
        success, response = self.run_test(
            "Create lore",
            "POST",
            "lore",
            200,
            data=lore_data
        )
        if success and 'id' in response:
            self.created_ids['lore'] = response['id']
            print(f"   Created lore ID: {response['id']}")
        return success

    def test_list_lore(self):
        """Test GET /api/lore?campaign_id= lists lore entries"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        success, response = self.run_test(
            "List lore",
            "GET",
            "lore",
            200,
            params={"campaign_id": campaign_id}
        )
        if success:
            print(f"   Found {len(response)} lore entries")
        return success

    def test_gm_roll(self):
        """Test POST /api/gm/roll rolls dice correctly"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        roll_data = {
            "campaign_id": campaign_id,
            "dice_expression": "1d20+5",
            "context": "Test roll for API testing"
        }
        success, response = self.run_test(
            "GM roll dice",
            "POST",
            "gm/roll",
            200,
            data=roll_data
        )
        if success and 'result' in response:
            result = response['result']
            print(f"   Roll result: {result.get('total', 'Unknown')}")
            print(f"   Expression: {result.get('expression', 'Unknown')}")
        return success

    def test_gm_check(self):
        """Test POST /api/gm/check resolves skill check with LLM narrative"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        check_data = {
            "campaign_id": campaign_id,
            "difficulty": "medium",
            "context": "Testing skill check resolution"
        }
        success, response = self.run_test(
            "GM skill check",
            "POST",
            "gm/check",
            200,
            data=check_data
        )
        if success:
            print(f"   Roll total: {response.get('total', 'Unknown')}")
            print(f"   DC: {response.get('dc', 'Unknown')}")
            print(f"   Passed: {response.get('passed', 'Unknown')}")
            if response.get('narrative'):
                print(f"   Narrative: {response['narrative'][:100]}...")
        return success

    def test_get_rules(self):
        """Test GET /api/rules?campaign_id= returns rules"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        success, response = self.run_test(
            "Get rules",
            "GET",
            "rules",
            200,
            params={"campaign_id": campaign_id}
        )
        if success:
            print(f"   Dice system: {response.get('dice_system', 'Unknown')}")
            print(f"   Critical enabled: {response.get('critical_enabled', 'Unknown')}")
        return success

    def test_create_channel(self):
        """Test POST /api/channels creates channel config"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        channel_data = {
            "campaign_id": campaign_id,
            "guild_id": "123456789",
            "channel_id": f"test-{datetime.now().strftime('%H%M%S')}",
            "channel_name": "test-channel",
            "mode": "ic"
        }
        success, response = self.run_test(
            "Create channel config",
            "POST",
            "channels",
            200,
            data=channel_data
        )
        if success and 'id' in response:
            self.created_ids['channel'] = response['id']
            print(f"   Created channel config ID: {response['id']}")
        return success

    def test_list_events(self):
        """Test GET /api/events?campaign_id= lists events"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        success, response = self.run_test(
            "List events",
            "GET",
            "events",
            200,
            params={"campaign_id": campaign_id}
        )
        if success:
            print(f"   Found {len(response)} events")
        return success

    def test_export_campaign(self):
        """Test GET /api/export/{campaign_id} exports campaign data"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        success, response = self.run_test(
            "Export campaign",
            "GET",
            f"export/{campaign_id}",
            200
        )
        if success and 'campaign' in response:
            print(f"   Exported campaign: {response['campaign'].get('name', 'Unknown')}")
            print(f"   Data sections: {list(response.keys())}")
        return success

def main():
    print("🎲 Starting GM Bot API Tests")
    print("=" * 50)
    
    tester = GMBotAPITester()
    
    # Core API tests
    tests = [
        tester.test_root_endpoint,
        tester.test_bot_status,
        tester.test_create_campaign,
        tester.test_list_campaigns,
        tester.test_get_active_campaign,
        tester.test_update_campaign,
        tester.test_create_npc,
        tester.test_list_npcs,
        tester.test_update_npc,
        tester.test_delete_npc,
        tester.test_create_lore,
        tester.test_list_lore,
        tester.test_gm_roll,
        tester.test_get_rules,
        tester.test_create_channel,
        tester.test_list_events,
        tester.test_export_campaign,
    ]
    
    # Skip LLM-dependent test for now as mentioned in requirements
    # tester.test_gm_check,
    
    failed_tests = []
    for test in tests:
        try:
            if not test():
                failed_tests.append(test.__name__)
        except Exception as e:
            print(f"❌ {test.__name__} crashed: {str(e)}")
            failed_tests.append(test.__name__)
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if failed_tests:
        print(f"❌ Failed tests: {', '.join(failed_tests)}")
        return 1
    else:
        print("✅ All tests passed!")
        return 0

if __name__ == "__main__":
    sys.exit(main())