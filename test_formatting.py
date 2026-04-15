#!/usr/bin/env python3
"""
Test script for GM output formatting features
"""
import requests
import sys
import json

class FormattingTester:
    def __init__(self, base_url="https://game-master-core.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.test_campaign_id = "6e3d6875-c5a0-4887-98d2-1f5510955bd7"
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, test_func):
        """Run a single test"""
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if test_func():
                self.tests_passed += 1
                print(f"✅ {name} - PASSED")
                return True
            else:
                print(f"❌ {name} - FAILED")
                return False
        except Exception as e:
            print(f"❌ {name} - ERROR: {str(e)}")
            return False

    def test_bot_status(self):
        """Test GET /api/bot/status works"""
        try:
            response = requests.get(f"{self.api_url}/bot/status", timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def test_campaigns_list(self):
        """Test GET /api/campaigns still works"""
        try:
            response = requests.get(f"{self.api_url}/campaigns", timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def test_multi_player_formatting(self):
        """Test multi-player response has **Name**: section headers"""
        scene_data = {
            "campaign_id": self.test_campaign_id,
            "channel_id": "test_channel_multi_format",
            "player_actions": [
                {
                    "discord_id": "123456789012345678",
                    "pc_name": "Viktor",
                    "message": "Ich schaue vorsichtig um die Ecke."
                },
                {
                    "discord_id": "987654321098765432", 
                    "pc_name": "Lena",
                    "message": "Ich halte meine Waffe bereit."
                }
            ]
        }

        try:
            response = requests.post(f"{self.api_url}/gm/scene-response", json=scene_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get('response'):
                    response_text = result['response']
                    print(f"   Response: {response_text[:200]}...")
                    
                    # Check for section headers
                    has_viktor_header = "**Viktor**:" in response_text
                    has_lena_header = "**Lena**:" in response_text
                    
                    print(f"   Has **Viktor**: header: {has_viktor_header}")
                    print(f"   Has **Lena**: header: {has_lena_header}")
                    
                    # Check for paragraph breaks between sections
                    has_paragraph_breaks = "\n\n" in response_text
                    print(f"   Has paragraph breaks: {has_paragraph_breaks}")
                    
                    return has_viktor_header and has_lena_header
                else:
                    print(f"   GM decided no response needed")
                    return True
            else:
                print(f"   Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"   Error: {str(e)}")
            return False

    def test_solo_player_no_header(self):
        """Test solo-player response has NO section header"""
        scene_data = {
            "campaign_id": self.test_campaign_id,
            "channel_id": "test_channel_solo_format",
            "player_actions": [
                {
                    "discord_id": "123456789012345678",
                    "pc_name": "Viktor",
                    "message": "Ich schaue vorsichtig um die Ecke und lausche nach Geräuschen."
                }
            ]
        }

        try:
            response = requests.post(f"{self.api_url}/gm/scene-response", json=scene_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get('response'):
                    response_text = result['response']
                    print(f"   Response: {response_text[:200]}...")
                    
                    # Check that there's NO section header for solo player
                    has_viktor_header = "**Viktor**:" in response_text
                    print(f"   Has **Viktor**: header: {has_viktor_header}")
                    
                    return not has_viktor_header
                else:
                    print(f"   GM decided no response needed")
                    return True
            else:
                print(f"   Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"   Error: {str(e)}")
            return False

    def test_response_length_under_1500(self):
        """Test response length is under 1500 chars"""
        scene_data = {
            "campaign_id": self.test_campaign_id,
            "channel_id": "test_channel_length",
            "player_actions": [
                {
                    "discord_id": "123456789012345678",
                    "pc_name": "Viktor",
                    "message": "Ich erkunde das gesamte Gebäude sehr gründlich, schaue in jeden Raum, untersuche alle Gegenstände, spreche mit allen NPCs und versuche alle möglichen Geheimnisse zu entdecken."
                }
            ]
        }

        try:
            response = requests.post(f"{self.api_url}/gm/scene-response", json=scene_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get('response'):
                    response_text = result['response']
                    response_length = len(response_text)
                    print(f"   Response length: {response_length} characters")
                    
                    is_acceptable = response_length <= 1500
                    print(f"   Under 1500 chars: {is_acceptable}")
                    
                    return is_acceptable
                else:
                    print(f"   GM decided no response needed")
                    return True
            else:
                print(f"   Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"   Error: {str(e)}")
            return False

    def test_message_driven_still_works(self):
        """Test POST /api/gm/message-driven still works"""
        message_data = {
            "campaign_id": self.test_campaign_id,
            "player_discord_id": "123456789012345678",
            "player_message": "Ich schaue mich um.",
            "channel_id": "test_channel_123"
        }

        try:
            response = requests.post(f"{self.api_url}/gm/message-driven", json=message_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                print(f"   Message-driven response: {result.get('response', 'null')[:100] if result.get('response') else 'null'}...")
                return True
            else:
                print(f"   Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"   Error: {str(e)}")
            return False

    def test_smart_context_still_works(self):
        """Test POST /api/memory/smart-context still works"""
        context_data = {
            "campaign_id": self.test_campaign_id,
            "player_discord_id": "123456789012345678",
            "current_message": "I look around the room for clues"
        }
        
        try:
            response = requests.post(f"{self.api_url}/memory/smart-context", json=context_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                stats = result.get('stats', {})
                print(f"   Smart context stats: PCs={stats.get('pcs', 0)}, NPCs={stats.get('npcs', 0)}")
                return True
            else:
                print(f"   Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"   Error: {str(e)}")
            return False

def main():
    print("🎲 Testing GM Output Formatting Features")
    print("=" * 50)
    
    tester = FormattingTester()
    
    # Run tests
    tests = [
        ("Bot Status", tester.test_bot_status),
        ("Campaigns List", tester.test_campaigns_list),
        ("Multi-Player Section Headers", tester.test_multi_player_formatting),
        ("Solo-Player No Header", tester.test_solo_player_no_header),
        ("Response Length Under 1500", tester.test_response_length_under_1500),
        ("Message-Driven Still Works", tester.test_message_driven_still_works),
        ("Smart Context Still Works", tester.test_smart_context_still_works),
    ]
    
    for test_name, test_func in tests:
        tester.run_test(test_name, test_func)
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("✅ All formatting tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())