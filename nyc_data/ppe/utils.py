def log_db_queries(f):
    from django.db import connection

    def wrapped(*args, **kwargs):
        before = len(connection.queries)
        res = f(*args, **kwargs)
        after = len(connection.queries)
        print(f"Total queries run by {f.__name__}: {after-before}")
        return res

    return wrapped
