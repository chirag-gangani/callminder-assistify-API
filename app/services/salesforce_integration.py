from simple_salesforce import Salesforce
from ..config import settings

class SalesforceIntegration:
    def __init__(self):
        self.username = settings.SALESFORCE_USERNAME
        self.password = settings.SALESFORCE_PASSWORD
        self.security_token = settings.SALESFORCE_SECURITY
        self.lead_history = []
        self.sf = Salesforce(
            username=self.username,
            password=self.password,
            security_token=self.security_token
        )
        self.initialized = True

    def create_lead(self, client_entities):
        if not self.initialized:
            return False
            
        try:
            lead_data = {
                'FirstName': client_entities.get('name', '').split()[0] if client_entities.get('name') else '',
                'LastName': ' '.join(client_entities.get('name', '').split()[1:]) if client_entities.get('name') and len(client_entities.get('name', '').split()) > 1 else 'Unknown',
                'Email': client_entities.get('email', ''),
                'Company': client_entities.get('company_name', 'Unknown Company'),
                'Industry': client_entities.get('industry', 'Unknown'),
                'LeadSource': 'AI Sales Call',
                'Status': 'Open - Not Contacted',
                'Description': f"Requirements: {', '.join(client_entities.get('requirements', []))}\nMeeting scheduled for: {client_entities.get('meeting_date', 'Not set')} at {client_entities.get('meeting_time', 'Not set')}"
            }
            
            response = self.sf.Lead.create(lead_data)
            if response.get('success', False):
                return True
            else:
                return False
                
        except Exception as e:
            return False

    def get_lead_history(self):
        return self.lead_history
    
    def verify_lead(self, lead_id):
        try:
            lead = self.sf.Lead.get(lead_id)
            return lead
        except Exception as e:
            return None