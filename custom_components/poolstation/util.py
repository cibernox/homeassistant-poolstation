from pypoolstation import Account

def create_account(session, email, password, logger):
  return Account(session, username=email, password=password, logger=logger)