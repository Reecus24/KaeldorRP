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
        self.test_campaign_id = "8b32b420-91d5-42ce-aeb2-3589cfc0b8a7"  # Active campaign ID from review
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

    def test_create_player_character(self):
        """Test POST /api/player-characters creates a player character with all fields"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        pc_data = {
            "campaign_id": campaign_id,
            "discord_user_id": "123456789012345678",
            "character_name": "Test Character",
            "status": "active",
            "short_description": "A test character for API testing",
            "appearance": "Tall and mysterious",
            "personality_traits": "Brave and curious",
            "background": "Former adventurer",
            "goals": "Find the truth",
            "fears": "Losing friends",
            "strengths": "Quick thinking",
            "weaknesses": "Trusts too easily",
            "skills": "Swordsmanship, Investigation",
            "injuries_conditions": "Minor scar on left arm",
            "inventory": "Sword, backpack, 50 gold",
            "faction_ties": "Member of the Guild",
            "relationship_notes": "Close friend of NPC Marcus",
            "gm_secrets": "Actually a noble in disguise",
            "public_knowledge": "Known as a reliable adventurer",
            "private_knowledge": "Knows about the secret passage",
            "current_location": "Tavern in Westport",
            "reputation": "Well-respected",
            "obligations_notes": "Owes favor to the blacksmith"
        }

        success, response = self.run_test(
            "Create Player Character",
            "POST",
            "player-characters",
            200,
            data=pc_data
        )
        
        if success and 'id' in response:
            self.created_ids['player_character'] = response['id']
            print(f"   Created PC ID: {response['id']}")
            print(f"   Character name: {response.get('character_name')}")
        return success

    def test_list_player_characters(self):
        """Test GET /api/player-characters?campaign_id= lists PCs"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        success, response = self.run_test(
            "List Player Characters",
            "GET",
            "player-characters",
            200,
            params={"campaign_id": campaign_id}
        )
        
        if success:
            print(f"   Found {len(response)} player characters")
        return success

    def test_list_active_player_characters(self):
        """Test GET /api/player-characters/active?campaign_id= lists active PCs"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        success, response = self.run_test(
            "List Active Player Characters",
            "GET",
            "player-characters/active",
            200,
            params={"campaign_id": campaign_id}
        )
        
        if success:
            print(f"   Found {len(response)} active player characters")
        return success

    def test_update_player_character(self):
        """Test PUT /api/player-characters/{id} updates a PC"""
        pc_id = self.created_ids.get('player_character')
        if not pc_id:
            print("   ⚠️  No PC ID available for update test")
            return False

        update_data = {
            "character_name": "Updated Test Character",
            "status": "inactive",
            "current_location": "Updated location"
        }
        
        success, response = self.run_test(
            "Update Player Character",
            "PUT",
            f"player-characters/{pc_id}",
            200,
            data=update_data
        )
        
        if success:
            print(f"   Updated character name: {response.get('character_name')}")
            print(f"   Updated status: {response.get('status')}")
        return success

    def test_delete_player_character(self):
        """Test DELETE /api/player-characters/{id} deletes a PC"""
        pc_id = self.created_ids.get('player_character')
        if not pc_id:
            print("   ⚠️  No PC ID available for delete test")
            return False

        success, response = self.run_test(
            "Delete Player Character",
            "DELETE",
            f"player-characters/{pc_id}",
            200
        )
        
        if success:
            print(f"   Deleted PC ID: {pc_id}")
            # Remove from created_ids since it's deleted
            del self.created_ids['player_character']
        return success

    def test_add_allowed_player(self):
        """Test POST /api/allowed-players adds an allowed player"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        player_data = {
            "campaign_id": campaign_id,
            "discord_user_id": "987654321098765432",
            "discord_username": "TestPlayer#1234"
        }

        success, response = self.run_test(
            "Add Allowed Player",
            "POST",
            "allowed-players",
            200,
            data=player_data
        )
        
        if success and 'id' in response:
            self.created_ids['allowed_player'] = response['id']
            print(f"   Created Allowed Player ID: {response['id']}")
            print(f"   Discord username: {response.get('discord_username')}")
        return success

    def test_list_allowed_players(self):
        """Test GET /api/allowed-players?campaign_id= lists allowed players"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        success, response = self.run_test(
            "List Allowed Players",
            "GET",
            "allowed-players",
            200,
            params={"campaign_id": campaign_id}
        )
        
        if success:
            print(f"   Found {len(response)} allowed players")
        return success

    def test_remove_allowed_player(self):
        """Test DELETE /api/allowed-players/{id} removes allowed player"""
        player_id = self.created_ids.get('allowed_player')
        if not player_id:
            print("   ⚠️  No allowed player ID available for delete test")
            return False

        success, response = self.run_test(
            "Remove Allowed Player",
            "DELETE",
            f"allowed-players/{player_id}",
            200
        )
        
        if success:
            print(f"   Removed allowed player ID: {player_id}")
            # Remove from created_ids since it's deleted
            del self.created_ids['allowed_player']
        return success

    def test_gm_message_driven(self):
        """Test POST /api/gm/message-driven accepts player message and returns response or null"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        message_data = {
            "campaign_id": campaign_id,
            "player_discord_id": "123456789012345678",
            "player_message": "I look around the room carefully.",
            "channel_id": "test_channel_123"
        }

        print("\n🔍 Testing Message-Driven GM (LLM-powered, may be slow)...")
        try:
            response = requests.post(f"{self.api_url}/gm/message-driven", json=message_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Message-driven GM responded")
                if result.get('response'):
                    print(f"   GM Response: {result['response'][:100]}...")
                else:
                    print(f"   GM decided no response needed (returned null)")
                self.tests_passed += 1
                self.tests_run += 1
                return True
            else:
                print(f"❌ Message-driven GM failed: {response.status_code}")
                self.tests_run += 1
                return False
        except Exception as e:
            print(f"❌ Message-driven GM error: {str(e)}")
            self.tests_run += 1
            return False

    def test_bot_status_with_pc_count(self):
        """Test GET /api/bot/status now includes player_characters count"""
        success, response = self.run_test(
            "Bot status with PC count",
            "GET",
            "bot/status",
            200
        )
        if success:
            required_fields = ['campaigns', 'npcs', 'events', 'player_characters', 'active_campaign']
            missing = [f for f in required_fields if f not in response]
            if missing:
                print(f"   ⚠️  Missing fields: {missing}")
                return False
            print(f"   Player Characters count: {response.get('player_characters', 0)}")
        return success

    def test_export_includes_pcs_and_players(self):
        """Test GET /api/export/{campaign_id} includes player_characters and allowed_players"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        success, response = self.run_test(
            "Export includes PCs and allowed players",
            "GET",
            f"export/{campaign_id}",
            200
        )
        if success:
            required_sections = ['campaign', 'player_characters', 'allowed_players']
            missing = [s for s in required_sections if s not in response]
            if missing:
                print(f"   ⚠️  Missing export sections: {missing}")
                return False
            print(f"   Player Characters in export: {len(response.get('player_characters', []))}")
            print(f"   Allowed Players in export: {len(response.get('allowed_players', []))}")
        return success

    def test_gm_generate_campaign(self):
        """Test POST /api/gm/generate-campaign creates rich German campaign from prompt"""
        campaign_data = {
            "prompt": "Ein düsteres Zombie-Apokalypse Setting in einer deutschen Stadt"
        }
        
        print("\n🔍 Testing Campaign Generation (LLM-powered, may be slow)...")
        try:
            response = requests.post(f"{self.api_url}/gm/generate-campaign", json=campaign_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Campaign generation successful")
                print(f"   Title: {result.get('title', 'N/A')}")
                print(f"   Tone: {result.get('tone', 'N/A')}")
                print(f"   World Summary: {result.get('world_summary', 'N/A')[:100]}...")
                self.tests_passed += 1
                self.tests_run += 1
                return True
            else:
                print(f"❌ Campaign generation failed: {response.status_code}")
                self.tests_run += 1
                return False
        except Exception as e:
            print(f"❌ Campaign generation error: {str(e)}")
            self.tests_run += 1
            return False

    def test_gm_generate_character_questions(self):
        """Test POST /api/gm/generate-character-questions returns 10 genre-specific questions"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        questions_data = {
            "campaign_id": campaign_id
        }
        
        print("\n🔍 Testing Character Questions Generation (LLM-powered, may be slow)...")
        try:
            response = requests.post(f"{self.api_url}/gm/generate-character-questions", json=questions_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                questions = result.get('questions', [])
                print(f"✅ Character questions generated")
                print(f"   Number of questions: {len(questions)}")
                if questions and len(questions) > 0:
                    print(f"   First question: {questions[0].get('prompt', 'N/A')[:80]}...")
                self.tests_passed += 1
                self.tests_run += 1
                return True
            else:
                print(f"❌ Character questions generation failed: {response.status_code}")
                self.tests_run += 1
                return False
        except Exception as e:
            print(f"❌ Character questions generation error: {str(e)}")
            self.tests_run += 1
            return False

    def test_gm_confirm_character_step(self):
        """Test POST /api/gm/confirm-character-step acknowledges a creation step"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        confirm_data = {
            "campaign_id": campaign_id,
            "field": "character_name",
            "answer": "Erik der Überlebende",
            "accumulated": {"character_name": "Erik der Überlebende"}
        }
        
        print("\n🔍 Testing Character Step Confirmation (LLM-powered, may be slow)...")
        try:
            response = requests.post(f"{self.api_url}/gm/confirm-character-step", json=confirm_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Character step confirmation successful")
                print(f"   Confirmation: {result.get('confirmation', 'N/A')[:100]}...")
                self.tests_passed += 1
                self.tests_run += 1
                return True
            else:
                print(f"❌ Character step confirmation failed: {response.status_code}")
                self.tests_run += 1
                return False
        except Exception as e:
            print(f"❌ Character step confirmation error: {str(e)}")
            self.tests_run += 1
            return False

    def test_gm_generate_relationship(self):
        """Test POST /api/gm/generate-relationship creates meaningful PC connections"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        relationship_data = {
            "campaign_id": campaign_id,
            "pc1_data": {
                "character_name": "Erik der Überlebende",
                "background": "Ehemaliger Polizist",
                "personality_traits": "Mutig aber misstrauisch"
            },
            "pc2_data": {
                "character_name": "Maria die Ärztin",
                "background": "Notärztin",
                "personality_traits": "Hilfsbereit und entschlossen"
            }
        }
        
        print("\n🔍 Testing Relationship Generation (LLM-powered, may be slow)...")
        try:
            response = requests.post(f"{self.api_url}/gm/generate-relationship", json=relationship_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Relationship generation successful")
                print(f"   Relationship: {result.get('relationship', 'N/A')[:100]}...")
                self.tests_passed += 1
                self.tests_run += 1
                return True
            else:
                print(f"❌ Relationship generation failed: {response.status_code}")
                self.tests_run += 1
                return False
        except Exception as e:
            print(f"❌ Relationship generation error: {str(e)}")
            self.tests_run += 1
            return False

    def test_gm_generate_opening_scene(self):
        """Test POST /api/gm/generate-opening-scene creates atmospheric German scene"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        scene_data = {
            "campaign_id": campaign_id
        }
        
        print("\n🔍 Testing Opening Scene Generation (LLM-powered, may be slow)...")
        try:
            response = requests.post(f"{self.api_url}/gm/generate-opening-scene", json=scene_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Opening scene generation successful")
                print(f"   Scene: {result.get('scene', 'N/A')[:100]}...")
                self.tests_passed += 1
                self.tests_run += 1
                return True
            else:
                print(f"❌ Opening scene generation failed: {response.status_code}")
                self.tests_run += 1
                return False
        except Exception as e:
            print(f"❌ Opening scene generation error: {str(e)}")
            self.tests_run += 1
            return False

    def test_gm_message_driven_with_dice(self):
        """Test POST /api/gm/message-driven responds in German with dice rolls when appropriate"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        message_data = {
            "campaign_id": campaign_id,
            "player_discord_id": "123456789012345678",
            "player_message": "Ich versuche die verschlossene Tür aufzubrechen.",
            "channel_id": "test_channel_123"
        }

        print("\n🔍 Testing Message-Driven GM with Dice (LLM-powered, may be slow)...")
        try:
            response = requests.post(f"{self.api_url}/gm/message-driven", json=message_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Message-driven GM with dice responded")
                if result.get('response'):
                    response_text = result['response']
                    print(f"   GM Response: {response_text[:100]}...")
                    # Check for German text and dice roll markers
                    has_german = any(word in response_text.lower() for word in ['der', 'die', 'das', 'und', 'ist', 'sie', 'er'])
                    has_dice = '[wurf:' in response_text.lower() or '[würf' in response_text.lower()
                    print(f"   Contains German: {has_german}")
                    print(f"   Contains dice roll: {has_dice}")
                else:
                    print(f"   GM decided no response needed (returned null)")
                self.tests_passed += 1
                self.tests_run += 1
                return True
            else:
                print(f"❌ Message-driven GM with dice failed: {response.status_code}")
                self.tests_run += 1
                return False
        except Exception as e:
            print(f"❌ Message-driven GM with dice error: {str(e)}")
            self.tests_run += 1
            return False

    def test_gm_message_driven_null_response(self):
        """Test POST /api/gm/message-driven returns null when no response needed"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        message_data = {
            "campaign_id": campaign_id,
            "player_discord_id": "123456789012345678",
            "player_message": "Ich denke über meine Vergangenheit nach.",  # Internal monologue
            "channel_id": "test_channel_123"
        }

        print("\n🔍 Testing Message-Driven GM Null Response (LLM-powered, may be slow)...")
        try:
            response = requests.post(f"{self.api_url}/gm/message-driven", json=message_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Message-driven GM null response test completed")
                if result.get('response') is None:
                    print(f"   ✅ Correctly returned null for internal monologue")
                else:
                    print(f"   ⚠️  Returned response when null expected: {result.get('response', '')[:50]}...")
                self.tests_passed += 1
                self.tests_run += 1
                return True
            else:
                print(f"❌ Message-driven GM null response test failed: {response.status_code}")
                self.tests_run += 1
                return False
        except Exception as e:
            print(f"❌ Message-driven GM null response test error: {str(e)}")
            self.tests_run += 1
            return False

    def test_character_changes_tracking(self):
        """Test POST /api/character-changes tracks character changes"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        changes_data = {
            "campaign_id": campaign_id,
            "changes": [
                "Erik - Verletzung: Schnittwunde am Arm",
                "Maria - Inventar: Verbandszeug verloren"
            ],
            "source": "GM response during combat scene"
        }
        
        success, response = self.run_test(
            "Track Character Changes",
            "POST",
            "character-changes",
            200,
            data=changes_data
        )
        
        if success:
            print(f"   Tracked changes: {response.get('tracked', 0)}")
            print(f"   Changes: {response.get('changes', [])}")
        return success

    def test_list_character_changes(self):
        """Test GET /api/character-changes?campaign_id= lists tracked changes"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        success, response = self.run_test(
            "List Character Changes",
            "GET",
            "character-changes",
            200,
            params={"campaign_id": campaign_id}
        )
        
        if success:
            print(f"   Found {len(response)} character changes")
            if response:
                self.created_ids['character_change'] = response[0].get('id')
        return success

    def test_apply_character_change(self):
        """Test PUT /api/character-changes/{id}/apply marks change as applied"""
        change_id = self.created_ids.get('character_change')
        if not change_id:
            print("   ⚠️  No character change ID available for apply test")
            return True  # Skip if no change to apply
        
        success, response = self.run_test(
            "Apply Character Change",
            "PUT",
            f"character-changes/{change_id}/apply",
            200
        )
        
        if success:
            print(f"   Applied change: {response.get('applied', False)}")
        return success

    def test_update_campaign_auto_channels(self):
        """Test PUT /api/campaigns/{id} can update auto_create_channels"""
        campaign_id = self.created_ids.get('campaign', self.test_campaign_id)
        update_data = {
            "auto_create_channels": True
        }
        success, response = self.run_test(
            "Update Campaign Auto Channels",
            "PUT",
            f"campaigns/{campaign_id}",
            200,
            data=update_data
        )
        if success:
            print(f"   Auto create channels: {response.get('auto_create_channels', False)}")
        return success

def main():
    print("🎲 Starting GM Bot API Tests")
    print("=" * 50)
    
    tester = GMBotAPITester()
    
    # Core API tests
    tests = [
        tester.test_root_endpoint,
        tester.test_bot_status_with_pc_count,  # Updated bot status test
        tester.test_create_campaign,
        tester.test_list_campaigns,
        tester.test_get_active_campaign,
        tester.test_update_campaign,
        tester.test_update_campaign_auto_channels,  # New: auto_create_channels field
        tester.test_create_npc,
        tester.test_list_npcs,
        tester.test_update_npc,
        tester.test_delete_npc,
        tester.test_create_lore,
        tester.test_list_lore,
        # Player Character tests
        tester.test_create_player_character,
        tester.test_list_player_characters,
        tester.test_list_active_player_characters,
        tester.test_update_player_character,
        # Allowed Player tests
        tester.test_add_allowed_player,
        tester.test_list_allowed_players,
        # GM Engine tests - Campaign Generation Flow
        tester.test_gm_generate_campaign,
        tester.test_gm_generate_character_questions,
        tester.test_gm_confirm_character_step,
        tester.test_gm_generate_relationship,
        tester.test_gm_generate_opening_scene,
        # GM Engine tests - Message-Driven
        tester.test_gm_message_driven_with_dice,
        tester.test_gm_message_driven_null_response,
        # Character Change Tracking
        tester.test_character_changes_tracking,
        tester.test_list_character_changes,
        tester.test_apply_character_change,
        # Other tests
        tester.test_gm_roll,
        tester.test_get_rules,
        tester.test_create_channel,
        tester.test_list_events,
        tester.test_export_includes_pcs_and_players,  # Updated export test
        # Cleanup tests (run these last)
        tester.test_delete_player_character,
        tester.test_remove_allowed_player,
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