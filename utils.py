import requests
from datetime import datetime
from models import db, MandiPrice

# Replace with your actual Resource API endpoint URL copied from data.gov.in
API_URL = API_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070?api-key=579b46466ec23bdd000001cdd3946e44ce4aad7&format=json&limit=100"

def sync_mandi_data():
    try:
        # Request data from data.gov.in API with a short timeout to handle failures gracefully
        response = requests.get(API_URL, timeout=10)
        
        if response.status_code == 200:
            data = response.json().get('records', [])
            
            new_records_count = 0
            for record in data:
                # Extract fields matching your dataset structure
                state = record.get('state')
                district = record.get('district')
                market = record.get('market')
                commodity = record.get('commodity')
                variety = record.get('variety', 'General')
                min_price = float(record.get('min_price', 0))
                max_price = float(record.get('max_price', 0))
                modal_price = float(record.get('modal_price', 0))
                
                # Parse date (adjust format based on API response date string)
                date_str = record.get('arrival_date') or str(datetime.now().date())
                arrival_date = datetime.strptime(date_str[:10], '%Y-%m-%d').date()
                
                # Check if this exact record already exists to avoid duplicates
                existing = MandiPrice.query.filter_by(
                    mandi_name=market, 
                    commodity=commodity, 
                    arrival_date=arrival_date
                ).first()
                
                if not existing:
                    new_entry = MandiPrice(
                        state=state,
                        district=district,
                        mandi_name=market,
                        commodity=commodity,
                        variety=variety,
                        min_price=min_price,
                        max_price=max_price,
                        modal_price=modal_price,
                        arrival_date=arrival_date
                    )
                    db.session.add(new_entry)
                    new_records_count += 1
            
            db.session.commit()
            return True, f"Successfully synced! Added {new_records_count} new records."
        else:
            return False, "API responded with an error status code."
            
    except requests.exceptions.RequestException:
        # Fallback: API is down or no internet, local database remains safe
        return False, "Network error: API unreachable. Local database is unaffected."