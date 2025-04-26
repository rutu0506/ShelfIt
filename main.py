import uuid

from tabulate import tabulate

from database import init_db, get_db

db = get_db()
session_user = None


def register():
    print('\n')
    username = input('Username: ')
    password = input('Password: ')
    print()

    # Check if user exists
    res = db.execute(
        'SELECT id FROM users WHERE username = ?', (username,)
    )
    if res.fetchone():
        print('User already exists!')
        print()
        return

    # Hash password
    hashed_password = str(uuid.uuid3(uuid.NAMESPACE_X500, password)).replace('-', '')

    # Insert new user
    db.execute(
        'INSERT INTO users (username, password) VALUES (?, ?)',
        (username, hashed_password)
    )
    db.commit()
    print('Registration successful!')
    print()


def login():
    print('\n')
    global session_user
    if session_user:
        print()
        print(f"User {session_user} has already logged in!")
        print()
        return
    print()
    username = input('Username: ')
    password = input('Password: ')
    print()

    hashed_password = str(uuid.uuid3(uuid.NAMESPACE_X500, password)).replace('-', '')

    # Check if user exists
    res = db.execute(
        'SELECT id FROM users WHERE username = ? AND password = ?', (username, hashed_password)
    )
    user = res.fetchone()
    if user:
        print('Login Successful!')
        print()
        session_user = user['id']
    else:
        print('User not found!')
        print()


def logout():
    print('\n')
    global session_user
    if session_user:
        session_user = None
        print()
        print('Logout Successful!')
        print()


def get_requests(books):
    book_id = int(input('Enter book id (book_id/0): '))
    print()
    req_res = db.execute(
        'SELECT requests.*, username as borrower '
        'FROM requests, users '
        'WHERE requests.status = ? AND book_id = ? AND users.id = borrower_id',
        ('requested', book_id)
    )
    requests = req_res.fetchall()
    if requests:
        print(f"Requests for book_id {book_id}")
        col_names = [description[0] for description in req_res.description]
        print(tabulate(requests, headers=col_names, tablefmt="pretty"))
        status = [book['status'] for book in books if book['id'] == book_id][0]
        if status == 'available':
            print()
            request_id = int(input('Accept a request? (request_id/0): '))
            print()
            if request_id:
                db.execute(
                    'UPDATE books '
                    'SET status = ?'
                    'WHERE id = (SELECT book_id FROM requests WHERE id = ?)', ('borrowed', request_id)
                )
                db.commit()
                db.execute(
                    'UPDATE requests '
                    'SET status = ?'
                    'WHERE id = ?', ('borrowed', request_id)
                )
                db.commit()
    else:
        print('No requests Found!')
        print()


def mark_book_available(books):
    book_id = int(input('Enter book id (book_id/0): '))
    print()
    status = [book['status'] for book in books if book['id'] == book_id][0]
    if status == 'available':
        print('Book already available!')
        print()
        return
    if book_id:
        db.execute(
            'UPDATE books '
            'SET status = ?'
            'WHERE id = ?', ('available', book_id)
        )
        db.commit()
        db.execute(
            'UPDATE requests '
            'SET status = ?'
            'WHERE book_id = ? AND status = ?', ('returned', book_id, 'borrowed')
        )
        db.commit()
        print(f"Marker book with {book_id} as available")
        print()


def get_books():
    res = db.execute(
        'SELECT b.*, '
        'CASE WHEN (SELECT COUNT(*) FROM requests WHERE status = ? AND book_id = b.id)>0 THEN ? '
        'ELSE ? END AS requested '
        'FROM books b WHERE owner_id = ?', ('requested', 'YES', 'NO', session_user,)
    )
    books = res.fetchall()
    if books:
        print('Books')
        col_names = [description[0] for description in res.description]
        print(tabulate(books, headers=col_names, tablefmt="pretty"))

        book_choices = {1: 'get_requests(books)', 2: 'mark_book_available(books)', 3: 'main()'}
        print()
        print('Choose from the following: ')
        [print(f"{key}: {value}") for key, value in book_choices.items()]
        print()
        eval(book_choices[int(input('Choice: '))])
    else:
        print('No books found!')
        print()


def view_profile():
    print('\n')
    if session_user:
        res = db.execute(
            'SELECT username FROM users WHERE id = ?', (session_user,)
        )
        user = res.fetchone()
        print()
        print(f"Username: {user['username']}")
        print()
        get_books()
    else:
        print()
        print('No active session!')
        print()


def add_book():
    print('\n')
    if session_user:
        print()
        title = input('Title: ')
        author = input('Author: ')
        description = input('Description: ')
        condition = input('Condition: ')
        category = input('Category: ')
        print()

        db.execute("""
                    INSERT INTO books (title, author, description, condition, category, owner_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (title, author, description, condition, category, session_user))
        db.commit()
    else:
        print()
        print('You need to Login!')
        print()


def browse_books():
    print('\n')
    print()
    keyword = input('Enter book title/author name: ')
    print()
    res = db.execute(
        'SELECT id, title, author '
        'FROM books '
        'WHERE title like ? OR author like ?',
        (f"%{keyword}%", f"%{keyword}%")
    )
    books = res.fetchall()
    if books:
        col_names = [description[0] for description in res.description]
        print(tabulate(books, headers=col_names, tablefmt="pretty"))
        print()
        book_id = int(input("View details of a particular book? Enter book id or 0: "))
        print()
        if book_id:
            view_book_details(book_id)
    else:
        print('No books found!')
        print()


def view_book_details(book_id):
    res = db.execute(
        'SELECT books.*, username as owner FROM books, users WHERE books.id = ? AND users.id = owner_id', (book_id,)
    )
    book = res.fetchall()
    if book:
        col_names = [description[0] for description in res.description]
        print(tabulate(book, headers=col_names, tablefmt="pretty"))
        if session_user:
            if book[0]['owner_id'] != session_user:
                cursor = db.execute("""
                        SELECT status FROM requests 
                        WHERE book_id = ? AND borrower_id = ? order by created_at desc limit 1
                    """, (book_id, session_user))
                book_request = cursor.fetchone()
                if not book_request or (book_request and book_request['status'] == 'returned'):
                    print()
                    ans = input('Request to borrow? Y/N: ')
                    print()
                    if ans == 'Y':
                        db.execute("""
                                INSERT INTO requests (book_id, borrower_id)
                                VALUES (?, ?)""", (book_id, session_user))
                        db.commit()
                elif book_request and book_request['status'] == 'borrowed':
                    print()
                    print('You already have the book!')
                    print()
                else:
                    print()
                    print('You have already requested for the book!')
                    print()
    else:
        print('Book not found!')
        print()


def main():
    options = {
        'active': {
            1: 'view_profile()',
            2: 'browse_books()',
            3: 'add_book()',
            4: 'logout()',
            0: 'quit(0)'
        },
        'inactive': {
            1: 'register()',
            2: 'login()',
            3: 'browse_books()',
            0: 'quit(0)'
        }
    }

    while True:
        if session_user:
            choices = options['active']
        else:
            choices = options['inactive']
        print()
        print('Choose from the following: ')
        [print(f"{key}: {value}") for key, value in choices.items()]
        print()
        eval(choices[int(input('Choice: '))])


if __name__ == '__main__':
    init_db()
    main()
    db.close()
