
from replit import db
import json
from datetime import datetime

def backup_bill_to_replit_db(bill):
    """Backup a bill to Replit DB"""
    try:
        # Create a serializable version of the bill
        bill_data = {
            'bill_number': bill.bill_number,
            'client_name': bill.client_name,
            'phone_number': bill.phone_number,
            'date': bill.date.isoformat(),
            'items': bill.items,
            'subtotal': bill.subtotal,
            'total': bill.total,
            'pdf_path': bill.pdf_path,
            'amount_paid': bill.amount_paid,
            'payment_status': bill.payment_status
        }
        
        # Save to Replit DB with a prefix for easy identification
        db[f'bill_{bill.bill_number}'] = bill_data
        
        # Also create a metadata key to track total number of bills
        try:
            all_bills = [k for k in db.keys() if k.startswith('bill_')]
            db['bills_metadata'] = {
                'total_count': len(all_bills),
                'last_updated': datetime.utcnow().isoformat()
            }
        except Exception:
            pass  # Ignore metadata errors
            
        return True
    except Exception as e:
        print(f"Error backing up bill to Replit DB: {str(e)}")
        return False

def get_all_bills_from_replit_db():
    try:
        from replit import db
        """Get all bills from Replit DB"""
        try:
            bill_keys = [k for k in db.keys() if k.startswith('bill_')]
            bills_data = []
            
            for key in bill_keys:
                bill_data = db.get(key)
                if bill_data:
                    # Convert date string back to datetime
                    if 'date' in bill_data and isinstance(bill_data['date'], str):
                        bill_data['date'] = datetime.fromisoformat(bill_data['date'])
                    bills_data.append(bill_data)
                    
            # Sort by date, newest first
            bills_data.sort(key=lambda x: x['date'], reverse=True)
            return bills_data
        except Exception as e:
            print(f"Error retrieving bills from Replit DB: {str(e)}")
            return []

def delete_bill_from_replit_db(bill_number):
    """Delete a bill from Replit DB"""
    try:
        key = f'bill_{bill_number}'
        if key in db:
            del db[key]
            return True
        return False
    except Exception as e:
        print(f"Error deleting bill from Replit DB: {str(e)}")
        return False
