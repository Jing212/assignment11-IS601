
"""
PostgreSQL integration tests for SQLAlchemy Calculation models.
"""

import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.database import Base
from app.models.user import User
from app.models.calculation import Calculation, Addition, Division


@pytest.fixture(scope="module")
def db_engine():
    """Create a database engine for integration tests."""
    database_url = settings.DATABASE_URL

    if not database_url.startswith("postgresql"):
        pytest.skip("PostgreSQL is required for this test.")

    engine = create_engine(database_url)

    # Ensure all registered model tables exist.
    Base.metadata.create_all(bind=engine)

    yield engine

    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Create a session and roll back test changes."""
    connection = db_engine.connect()
    transaction = connection.begin()

    TestSession = sessionmaker(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
    )

    session = TestSession()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_user(db_session):
    """Create a user required by the Calculation foreign key."""
    unique_id = uuid.uuid4().hex

    user = User(
        username=f"test_{unique_id}",
        email=f"test_{unique_id}@example.com",
    )

    db_session.add(user)
    db_session.flush()

    return user


def test_save_and_retrieve_addition(db_session, test_user):
    """Verify an addition is stored and retrieved from PostgreSQL."""
    calculation = Calculation.create(
        calculation_type="addition",
        user_id=test_user.id,
        inputs=[10, 5],
    )
    calculation.result = calculation.get_result()

    db_session.add(calculation)
    db_session.commit()

    stored = db_session.execute(
        select(Calculation).where(Calculation.id == calculation.id)
    ).scalar_one()

    assert isinstance(stored, Addition)
    assert stored.inputs == [10, 5]
    assert stored.result == 15
    assert stored.user_id == test_user.id
    assert stored.a == 10
    assert stored.b == 5


def test_save_and_retrieve_division(db_session, test_user):
    """Verify a division record persists with the correct result."""
    calculation = Calculation.create(
        calculation_type="division",
        user_id=test_user.id,
        inputs=[100, 5],
    )
    calculation.result = calculation.get_result()

    db_session.add(calculation)
    db_session.commit()

    stored = db_session.execute(
        select(Calculation).where(Calculation.id == calculation.id)
    ).scalar_one()

    assert isinstance(stored, Division)
    assert stored.inputs == [100, 5]
    assert stored.result == 20
    assert stored.a == 100
    assert stored.b == 5


def test_invalid_calculation_type(test_user):
    """Verify unsupported calculation types are rejected."""
    with pytest.raises(ValueError, match="Unsupported calculation type"):
        Calculation.create(
            calculation_type="modulus",
            user_id=test_user.id,
            inputs=[10, 3],
        )


def test_division_by_zero(test_user):
    """Verify division by zero is rejected before persistence."""
    calculation = Calculation.create(
        calculation_type="division",
        user_id=test_user.id,
        inputs=[10, 0],
    )

    with pytest.raises(ValueError, match="Cannot divide by zero"):
        calculation.get_result()
