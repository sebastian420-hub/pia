from pia.core.database import DatabaseManager
db = DatabaseManager()
db.execute_query("UPDATE analysis_queue SET status = 'PENDING', error_message = NULL WHERE status = 'FAILED'")
print('Failed jobs reset to PENDING.')
