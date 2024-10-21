import csv
from openai import OpenAI
from collections import defaultdict
import time
import random
import re
import os
import sys

# Initialize the OpenAI client with API key from environment variable
client = OpenAI(api_key=os.environ.get('API_KEY'))

def read_csv(file_path):
    transactions = []
    with open(file_path, 'r') as csvfile:
        reader = csv.reader(csvfile, quotechar='"', delimiter=',')
        next(reader)  # Skip the header row
        for row in reader:
            if len(row) == 5:  # Ensure the row has the expected number of fields
                status, date, description, debit, credit = row
                amount = debit if debit else credit
                transactions.append({
                    'Status': status,
                    'Date': date,
                    'Description': description,
                    'Amount': amount if amount.strip() else '0',  # Default to '0' if Amount is empty
                    'Type': 'Debit' if debit else 'Credit'
                })
    return transactions

def clean_category(category):
    category = category.lower()
    category = re.sub(r'.*?(?:category is|categorized as|categorized under)\s*["\']?([^"\']+)["\']?.*', r'\1', category, flags=re.IGNORECASE)
    category = category.strip()
    return ' '.join(word.capitalize() for word in category.split())

def categorize_transaction(description, max_retries=5, base_delay=1):
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that categorizes expenses. Respond with only the category name."},
                    {"role": "user", "content": f"Categorize this expense into a broad category (e.g., Groceries, Dining, Transportation, Entertainment, Utilities, etc.):\nDescription: {description}"}
                ],
                max_tokens=10
            )
            category = response.choices[0].message.content.strip()
            return clean_category(category)
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"API call failed after {max_retries} attempts: {str(e)}. Using fallback categorization.")
                return fallback_categorize(description)
            else:
                delay = (2 ** attempt) * base_delay + random.uniform(0, 0.1 * (2 ** attempt))
                print(f"API call failed. Retrying in {delay:.2f} seconds...")
                time.sleep(delay)

def fallback_categorize(description):
    categories = {
        'Grocery': ['GROCERY', 'SUPERMARKET', 'FOOD MART'],
        'Dining': ['RESTAURANT', 'CAFE', 'COFFEE', 'PIZZA', 'BURGER'],
        'Transportation': ['UBER', 'LYFT', 'TAXI', 'GAS', 'FUEL', 'TRANSIT'],
        'Utilities': ['ELECTRIC', 'WATER', 'GAS', 'INTERNET', 'PHONE'],
        'Entertainment': ['CINEMA', 'THEATRE', 'MOVIE', 'NETFLIX', 'SPOTIFY'],
    }
    
    description_upper = description.upper()
    for category, keywords in categories.items():
        if any(keyword in description_upper for keyword in keywords):
            return category
    return 'Other'  # Default category if no match is found

def categorize_expenses(transactions):
    categorized = []
    for transaction in transactions:
        category = categorize_transaction(transaction['Description'])
        categorized.append({**transaction, 'Category': category})
    return categorized

def summarize_expenses(categorized_transactions):
    summary = defaultdict(float)
    for transaction in categorized_transactions:
        amount = float(transaction['Amount'])
        if transaction['Type'] == 'Credit':
            amount = -amount  # Subtract the amount if it's a credit
        summary[transaction['Category']] += amount
    return dict(summary)

def write_output_csv(categorized_transactions, output_file):
    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = ['Date', 'Description', 'Amount', 'Category', 'Type']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for transaction in categorized_transactions:
            writer.writerow({
                'Date': transaction['Date'],
                'Description': transaction['Description'],
                'Amount': transaction['Amount'],
                'Category': transaction['Category'],
                'Type': transaction['Type']
            })

def main(input_file):
    transactions = read_csv(input_file)
    categorized = categorize_expenses(transactions)
    summary = summarize_expenses(categorized)
    
    print("Expense Summary:")
    for category, amount in summary.items():
        print(f"{category}: ${amount:.2f}")
    
    output_file = 'categorized_' + os.path.basename(input_file)
    write_output_csv(categorized, output_file)
    print(f"\nDetailed transactions have been written to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script_name.py <input_csv_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    main(input_file)
