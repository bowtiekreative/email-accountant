"""Use local Llama model to classify ambiguous transactions."""
import sys, os, json, re, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import EmailAccountantDB
from datetime import datetime

LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLAMA_CLI = os.path.expanduser("~/.local/bin/llama/llama-cli")
MODEL_PATH = "/opt/data/.cache/huggingface/hub/models--bartowski--Llama-3.2-3B-Instruct-GGUF/snapshots/5ab33fa94d1d04e903623ae72c95d1696f09f9e8/Llama-3.2-3B-Instruct-Q4_K_M.gguf"

SYSTEM_PROMPT = """You are a financial transaction classifier. For each transaction, determine:
- domain: personal or business
- type: income or expense  
- category: one of the standard categories
- reasoning: one short sentence

Standard categories:
Business expense: Software & Subscriptions, Marketing & Advertising, Internet & Telecom, Office Supplies, Professional Services, Equipment & Hardware, Travel & Meals, uncategorized-business
Business income: Client Payments, Consulting Fees, uncategorized-business  
Personal expense: Entertainment, Dining Out, Shopping, Groceries, Housing, Healthcare, Transport, Miscellaneous, uncategorized-personal
Personal income: Employment Salary, Gifts, Investment Income, Miscellaneous

PayPal rule: Payments TO merchants (you paid/sent) = expense. Payments FROM people (you received) = income.
If PayPal payment is to a business service (Hostinger, GitHub, AWS, Slack, OpenRouter, Anthropic, Stripe) = business expense.
If to a personal service (Uber, Netflix, DoorDash, restaurant) = personal expense.
If payment received from a person = business income (client payment).

Respond with a JSON array of classifications, one per transaction."""


def classify_batch(transactions):
    """Send a batch of transactions to the local LLM via subprocess (more reliable)."""
    items = []
    for t in transactions:
        subject = (t.get('subject') or '')[:100]
        items.append(f"- Merchant: {t['merchant'] or 'Unknown'} | Amount: ${t['amount']:.2f} | Subject: {subject}")
    
    user_prompt = "Classify these transactions:\n\n" + "\n".join(items) + "\n\nRespond ONLY with a JSON array: [{\"domain\": \"...\", \"type\": \"...\", \"category\": \"...\", \"reasoning\": \"...\"}]"
    full_prompt = f"<|system|>You are a financial transaction classifier. Determine domain (personal/business), type (income/expense), and category for each.</s>\n<|user|>{user_prompt}</s>\n<|assistant|>"
    
    try:
        result = subprocess.run(
            [LLAMA_CLI, '-m', MODEL_PATH, '--prompt', full_prompt, '-n', 512, '-t', '2', '-c', '4096', '--temp', '0.05', '--no-display-prompt'],
            capture_output=True, text=True, timeout=180,
            env={**os.environ, 'LD_LIBRARY_PATH': os.path.expanduser('~/.local/bin/llama')}
        )
        content = result.stdout.strip()
        
        # Extract JSON array from response
        json_match = re.search(r'\[.*?\]', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        
        # Try single object
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            obj = json.loads(json_match.group(0))
            return [obj]
        
        print(f"  ⚠️  Could not parse: {content[:150]}")
        return None
    except subprocess.TimeoutExpired:
        print(f"  ⏰  Timed out", end="")
        return None
    except Exception as e:
        print(f"  ⚠️  Error: {e}", end="")
        return None


# Main
yr = datetime.now().year
db = EmailAccountantDB(yr)

# Get transactions needing review with email info
rows = db._conn.execute("""
    SELECT t.id, t.merchant_name, t.amount, t.domain, t.transaction_type, 
           t.category, t.classification_confidence,
           COALESCE(e.subject, t.email_subject) as subject,
           COALESCE(e.from_email, t.email_from) as from_email
    FROM transactions t
    LEFT JOIN emails e ON e.id = t.email_id
    WHERE t.needs_review = 1 OR t.domain = 'unknown' OR t.classification_confidence < 0.5
    ORDER BY t.amount DESC
""").fetchall()

print(f"📊 {len(rows)} transactions to classify with local LLM\n")

batch_size = 4
updated = 0
failed = 0

for i in range(0, len(rows), batch_size):
    batch = rows[i:i+batch_size]
    txn_list = [
        {"id": r["id"], "merchant": r["merchant_name"], "amount": r["amount"],
         "subject": r["subject"], "from_email": r["from_email"]}
        for r in batch
    ]
    
    print(f"📨 Batch {i//batch_size + 1}/{(len(rows)-1)//batch_size + 1} ({i+1}-{i+len(batch)} of {len(rows)})...", end=" ", flush=True)
    
    classifications = classify_batch(txn_list)
    
    if classifications:
        for j, cls in enumerate(classifications):
            if j < len(batch):
                txn_id = batch[j]["id"]
                domain = cls.get("domain", "unknown")
                tx_type = cls.get("type", "unknown")
                category = cls.get("category", "uncategorized")
                reasoning = cls.get("reasoning", "")
                
                # Validate
                if domain not in ("personal", "business", "unknown"):
                    domain = "unknown"
                if tx_type not in ("income", "expense", "unknown"):
                    tx_type = "unknown"
                
                db._conn.execute("""
                    UPDATE transactions SET
                        domain = ?,
                        transaction_type = ?,
                        category = ?,
                        classification_method = 'llm',
                        classification_confidence = 0.75,
                        is_deductible = CASE WHEN ? = 'business' AND ? = 'expense' THEN 1 ELSE 0 END,
                        deduction_rate = CASE WHEN ? = 'business' AND ? = 'expense' AND ? IN ('Travel & Meals', 'Meals & Entertainment') THEN 0.5 WHEN ? = 'business' AND ? = 'expense' THEN 1.0 ELSE 0.0 END,
                        needs_review = 0,
                        flag_reason = ?
                    WHERE id = ?
                """, (domain, tx_type, category, 
                      domain, tx_type,
                      domain, tx_type, category,
                      domain, tx_type,
                      reasoning[:200], txn_id))
                updated += 1
                print(f"✓", end="")
            else:
                print(f"✗", end="")
    else:
        # Fallback: simple rule-based for PayPal
        for txn in txn_list:
            subject = (txn.get("subject") or "").lower()
            merchant = (txn.get("merchant") or "").lower()
            from_email = (txn.get("from_email") or "").lower()
            
            # Check if it's income or expense
            is_expense = any(kw in subject for kw in ["payment to", "you paid", "you sent", "receipt for your payment"])
            is_income = any(kw in subject for kw in ["payment received", "you received", "received from", "money received"])
            
            if is_expense:
                tx_type = "expense"
            elif is_income:
                tx_type = "income"
            else:
                tx_type = "unknown"
            
            # Determine business vs personal
            domain = "unknown"
            category = "uncategorized"
            
            if tx_type == "income":
                domain = "business"
                category = "Client Payments"
            elif tx_type == "expense":
                domain = "personal"
                category = "Miscellaneous"
            
            if merchant and tx_type == "expense":
                business_payees = ["hostinger", "github", "openrouter", "anthropic", "stripe", 
                                   "meta", "facebook", "instagram", "elementor", "facetwp",
                                   "robomotion", "mainfunc", "digitalocean", "aws"]
                personal_payees = ["uber", "doordash", "netflix", "spotify", "google play"]
                
                if any(p in merchant for p in business_payees):
                    domain = "business"
                    category = "Software & Subscriptions"
                elif any(p in merchant for p in personal_payees):
                    domain = "personal"
                    category = "Entertainment"
            
            db._conn.execute("""
                UPDATE transactions SET
                    domain = ?, transaction_type = ?, category = ?,
                    classification_method = 'rule_fallback',
                    classification_confidence = 0.5,
                    is_deductible = CASE WHEN ? = 'business' AND ? = 'expense' THEN 1 ELSE 0 END,
                    deduction_rate = CASE WHEN ? = 'business' AND ? = 'expense' THEN 1.0 ELSE 0.0 END,
                    needs_review = 1
                WHERE id = ?
            """, (domain, tx_type, category, domain, tx_type, domain, tx_type, txn["id"]))
            updated += 1
            print(f"·", end="")
        failed += 1
    
    db._conn.commit()
    print(f" ({updated} updated)")
    time.sleep(0.5)  # Rate limit

# Final summary
remaining = db._conn.execute("SELECT COUNT(*) as c FROM transactions WHERE needs_review = 1 OR domain = 'unknown'").fetchone()
print(f"\n{'='*60}")
print(f"✅ LLM Classification Complete")
print(f"{'='*60}")
print(f"   Updated: {updated}")
print(f"   Still needs review: {remaining['c']}")

# Show updated categories
cats = db._conn.execute("""
    SELECT domain, transaction_type, category, COUNT(*) as c, ROUND(SUM(amount),2) as total
    FROM transactions GROUP BY domain, transaction_type, category ORDER BY total DESC
""").fetchall()
print(f"\n📊 Updated Category Breakdown:")
for s in cats:
    print(f"   {s['domain']:10s} | {s['transaction_type']:8s} | {s['category']:30s} | {s['c']:3d}x | ${s['total']:>8.2f}")

db.close()
