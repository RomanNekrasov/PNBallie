from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///./pnballie.db"

engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
