-- Fix account state for anmolsinha4321@gmail.com
-- This resets the account from token_revoked to active state

UPDATE email_accounts
SET 
    account_state = 'active',
    last_error_message = NULL,
    is_active = true,
    connection_status = 'CONNECTED',
    updated_at = NOW()
WHERE 
    email_address = 'anmolsinha4321@gmail.com'
    AND id = '13672c43-c992-48e7-bdf5-c119b46a5ba9';

-- Verify the update
SELECT 
    id,
    email_address,
    account_state,
    is_active,
    connection_status,
    last_error_message,
    updated_at
FROM email_accounts
WHERE email_address = 'anmolsinha4321@gmail.com';
