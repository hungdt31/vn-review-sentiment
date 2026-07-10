import sys

def check_tables():
    import psycopg2
    from src.config import DB_CONFIG
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            # Kiểm tra xem bảng 'reviews' đã tồn tại trong schema public chưa
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                      AND table_name = 'reviews'
                );
            """)
            exists = cur.fetchone()[0]
            return exists
    except Exception as e:
        print(f"Lỗi kiểm tra Database: {e}", file=sys.stderr)
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    if check_tables():
        print("tables_exist")
        sys.exit(0) # Trả về exit code 0 nếu bảng đã tồn tại
    else:
        print("tables_not_exist")
        sys.exit(1) # Trả về exit code 1 nếu bảng chưa tồn tại
