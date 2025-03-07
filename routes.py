import os
from datetime import datetime
from flask import render_template, request, jsonify, send_file, flash, redirect, url_for
from app import app, db

# Login route removed
from models import Bill
from utils.pdf_generator import generate_pdf

# Set up a persistent folder for PDFs in deployment
if os.environ.get("REPLIT_DEPLOYMENT") == "1":
    UPLOAD_FOLDER = '/home/runner/appdata/generated_pdfs'
else:
    UPLOAD_FOLDER = 'generated_pdfs'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/bills')
def bills():
    try:
        bills = Bill.query.all()
        return render_template('bills.html', bills=bills)
    except Exception as e:
        app.logger.error(f"Error in bills route: {str(e)}")
        return render_template('bills.html', bills=[])

@app.route('/generate_bill', methods=['POST'])
def generate_bill():
    try:
        data = request.form
        items = []

        for i in range(len(request.form.getlist('item_name[]'))):
            items.append({
                'name': request.form.getlist('item_name[]')[i],
                'unit': request.form.getlist('unit[]')[i],
                'quantity': float(request.form.getlist('quantity[]')[i]),
                'price': float(request.form.getlist('price[]')[i]),
                'amount': float(request.form.getlist('amount[]')[i])
            })

        bill_number = f"FAB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        pdf_filename = f"{bill_number}.pdf"
        pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)

        total = float(data['total'])
        amount_paid = float(data['amount_paid'])

        # Determine payment status
        payment_status = 'pending'
        if amount_paid >= total:
            payment_status = 'paid'
        elif amount_paid > 0:
            payment_status = 'partial'

        new_bill = Bill(
            bill_number=bill_number,
            client_name=data['client_name'],
            phone_number=data['phone_number'],
            date=datetime.utcnow(),
            items=items,
            subtotal=float(data['subtotal']),
            total=total,
            amount_paid=amount_paid,
            payment_status=payment_status,
            pdf_path=pdf_path
        )

        # Generate PDF before saving to database to catch any PDF generation errors
        generate_pdf(new_bill, pdf_path)

        db.session.add(new_bill)
        db.session.commit()
        
        # Backup to Replit DB
        from utils.db_backup import backup_bill_to_replit_db
        backup_bill_to_replit_db(new_bill)

        flash('Bill generated successfully!', 'success')
        return redirect(url_for('bills'))

    except Exception as e:
        app.logger.error(f"Error generating bill: {str(e)}")
        flash('Error generating bill. Please try again.', 'danger')
        return redirect(url_for('index'))

@app.route('/download_pdf/<int:bill_id>')
def download_pdf(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    return send_file(bill.pdf_path, as_attachment=True)

@app.route('/edit_payment/<int:bill_id>')
def edit_payment(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    return render_template('edit_payment.html', bill=bill)

@app.route('/update_payment/<int:bill_id>', methods=['POST'])
def update_payment(bill_id):
    try:
        bill = Bill.query.get_or_404(bill_id)
        new_payment = float(request.form['new_payment'])

        # Validate payment amount
        pending_amount = bill.total - bill.amount_paid
        if new_payment <= 0 or new_payment > pending_amount:
            flash('Invalid payment amount', 'danger')
            return redirect(url_for('edit_payment', bill_id=bill.id))

        # Update payment information
        bill.amount_paid += new_payment

        # Update payment status
        if bill.amount_paid >= bill.total:
            bill.payment_status = 'paid'
        else:
            bill.payment_status = 'partial'

        # Record this payment in payment history
        from models import PaymentHistory
        payment_record = PaymentHistory(
            bill_id=bill.id,
            bill_number=bill.bill_number,
            client_name=bill.client_name,
            payment_date=datetime.utcnow(),
            amount=new_payment
        )
        db.session.add(payment_record)
        db.session.commit()

        # Backup updated bill to Replit DB
        from utils.db_backup import backup_bill_to_replit_db
        backup_bill_to_replit_db(bill)

        # Generate updated PDF
        generate_pdf(bill, bill.pdf_path)

        flash('Payment updated successfully!', 'success')
        return redirect(url_for('bills'))

    except Exception as e:
        app.logger.error(f"Error updating payment: {str(e)}")
        flash('Error updating payment. Please try again.', 'danger')
        return redirect(url_for('edit_payment', bill_id=bill_id))

@app.route('/edit_bill/<int:bill_id>')
def edit_bill(bill_id):
    try:
        bill = Bill.query.get_or_404(bill_id)
        
        # Only allow editing of pending or partial payments
        if bill.payment_status == 'paid':
            flash('Paid bills cannot be edited.', 'danger')
            return redirect(url_for('bills'))
            
        return render_template('edit_bill.html', bill=bill)
    except Exception as e:
        app.logger.error(f"Error in edit_bill route: {str(e)}")
        flash('Error loading bill. Please try again.', 'danger')
        return redirect(url_for('bills'))

@app.route('/update_bill/<int:bill_id>', methods=['POST'])
def update_bill(bill_id):
    try:
        bill = Bill.query.get_or_404(bill_id)
        
        # Only allow editing of pending or partial payments
        if bill.payment_status == 'paid':
            flash('Paid bills cannot be edited.', 'danger')
            return redirect(url_for('bills'))
            
        data = request.form
        items = []

        for i in range(len(request.form.getlist('item_name[]'))):
            items.append({
                'name': request.form.getlist('item_name[]')[i],
                'unit': request.form.getlist('unit[]')[i],
                'quantity': float(request.form.getlist('quantity[]')[i]),
                'price': float(request.form.getlist('price[]')[i]),
                'amount': float(request.form.getlist('amount[]')[i])
            })

        # Update bill details
        bill.client_name = data['client_name']
        bill.phone_number = data['phone_number']
        bill.items = items
        bill.subtotal = float(data['subtotal'])
        new_total = float(data['total'])
        
        # Handle the case where total changes but payment was made
        if bill.amount_paid > 0:
            if new_total < bill.amount_paid:
                # If new total is less than amount already paid
                bill.amount_paid = new_total
                bill.payment_status = 'paid'
            else:
                # Recalculate payment status based on new total
                if bill.amount_paid >= new_total:
                    bill.payment_status = 'paid'
                else:
                    bill.payment_status = 'partial'
        
        bill.total = new_total

        # Generate updated PDF
        generate_pdf(bill, bill.pdf_path)

        db.session.commit()
        
        # Backup updated bill to Replit DB
        from utils.db_backup import backup_bill_to_replit_db
        backup_bill_to_replit_db(bill)

        flash('Bill updated successfully!', 'success')
        return redirect(url_for('bills'))

    except Exception as e:
        app.logger.error(f"Error updating bill: {str(e)}")
        db.session.rollback()
        flash('Error updating bill. Please try again.', 'danger')
        return redirect(url_for('edit_bill', bill_id=bill_id))

@app.route('/delete_bill/<int:bill_id>', methods=['POST'])
def delete_bill(bill_id):
    try:
        bill = Bill.query.get_or_404(bill_id)

        # Only allow deletion of paid bills
        if bill.payment_status != 'paid':
            flash('Only fully paid bills can be deleted.', 'danger')
            return redirect(url_for('bills'))

        # Delete the PDF file if it exists
        if os.path.exists(bill.pdf_path):
            os.remove(bill.pdf_path)

        # Delete the bill from database
        db.session.delete(bill)
        db.session.commit()
        
        # Remove from Replit DB as well
        from utils.db_backup import delete_bill_from_replit_db
        delete_bill_from_replit_db(bill.bill_number)

        flash('Bill deleted successfully!', 'success')
        return redirect(url_for('bills'))

    except Exception as e:
        app.logger.error(f"Error deleting bill: {str(e)}")
        flash('Error deleting bill. Please try again.', 'danger')
        return redirect(url_for('bills'))

@app.route('/payment_history')
def payment_history():
    try:
        # Create a model to track payments with date
        from models import PaymentHistory
        
        # First check if any payment records exist
        payment_records = PaymentHistory.query.order_by(PaymentHistory.payment_date.desc()).all()
        
        # If no records but we have bills with payments, create payment history records
        if len(payment_records) == 0:
            bills_with_payments = Bill.query.filter(Bill.amount_paid > 0).all()
            for bill in bills_with_payments:
                # For existing bills, assume payment was made on the bill date
                new_payment = PaymentHistory(
                    bill_id=bill.id,
                    bill_number=bill.bill_number,
                    client_name=bill.client_name,
                    payment_date=bill.date,
                    amount=bill.amount_paid
                )
                db.session.add(new_payment)
            
            try:
                db.session.commit()
                # Refresh payment records
                payment_records = PaymentHistory.query.order_by(PaymentHistory.payment_date.desc()).all()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error creating payment history: {str(e)}")
        
        # Group payments by client name
        clients = {}
        for record in payment_records:
            if record.client_name not in clients:
                clients[record.client_name] = []
            clients[record.client_name].append(record)
            
        return render_template('payment_history.html', payment_records=payment_records, clients=clients)
        
    except Exception as e:
        app.logger.error(f"Error in payment_history route: {str(e)}")
        flash('Error loading payment history. Please try again.', 'danger')
        return redirect(url_for('bills'))