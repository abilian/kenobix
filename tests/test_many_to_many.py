"""
Tests for KenobiX ODM ManyToMany (many-to-many relationships).

Tests the ManyToMany descriptor for many-to-many relationships through junction tables.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from kenobix import KenobiX, ManyToMany
from kenobix.odm import Document


@pytest.fixture
def db_path(tmp_path):
    """Provide temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db(db_path):
    """Provide KenobiX database instance."""
    database = KenobiX(str(db_path))
    Document.set_database(database)
    yield database
    database.close()


# Test Models
@dataclass
class Student(Document):
    """Student model with many-to-many relationship to Course."""

    class Meta:
        collection_name = "students"
        indexed_fields = ["student_id"]

    student_id: int
    name: str


@dataclass
class Course(Document):
    """Course model with many-to-many relationship to Student."""

    class Meta:
        collection_name = "courses"
        indexed_fields = ["course_id"]

    course_id: int
    title: str


# Add relationships after both classes are defined
Student.courses = ManyToMany(
    Course, through="enrollments", local_field="student_id", remote_field="course_id"
)

Course.students = ManyToMany(
    Student, through="enrollments", local_field="course_id", remote_field="student_id"
)


class TestManyToManyBasics:
    """Test basic ManyToMany functionality."""

    def test_many_to_many_all(self, db):
        """Test getting all related objects."""
        # Create student and courses
        student = Student(student_id=1, name="Alice")
        student.save()

        course1 = Course(course_id=101, title="Math")
        course1.save()

        course2 = Course(course_id=102, title="Science")
        course2.save()

        course3 = Course(course_id=103, title="History")
        course3.save()

        # Add enrollments
        student_loaded = Student.get(student_id=1)
        student_loaded.courses.add(course1)
        student_loaded.courses.add(course2)
        student_loaded.courses.add(course3)

        # Get all courses
        courses = student_loaded.courses.all()
        assert len(courses) == 3
        course_titles = {c.title for c in courses}
        assert course_titles == {"Math", "Science", "History"}

    def test_many_to_many_empty(self, db):
        """Test many-to-many with no related objects."""
        student = Student(student_id=1, name="Alice")
        student.save()

        student_loaded = Student.get(student_id=1)
        courses = student_loaded.courses.all()
        assert len(courses) == 0

    def test_many_to_many_filter(self, db):
        """Test filtering related objects."""
        student = Student(student_id=1, name="Alice")
        student.save()

        Course(course_id=101, title="Math").save()
        Course(course_id=102, title="Science").save()
        Course(course_id=103, title="Math").save()  # Duplicate title

        student_loaded = Student.get(student_id=1)
        math_course = Course.get(course_id=101)
        science_course = Course.get(course_id=102)
        math2_course = Course.get(course_id=103)

        student_loaded.courses.add(math_course)
        student_loaded.courses.add(science_course)
        student_loaded.courses.add(math2_course)

        # Filter by title
        math_courses = student_loaded.courses.filter(title="Math")
        assert len(math_courses) == 2

    def test_many_to_many_count(self, db):
        """Test counting related objects."""
        student = Student(student_id=1, name="Alice")
        student.save()

        Course(course_id=101, title="Math").save()
        Course(course_id=102, title="Science").save()
        Course(course_id=103, title="History").save()

        student_loaded = Student.get(student_id=1)
        for course_id in [101, 102, 103]:
            course = Course.get(course_id=course_id)
            student_loaded.courses.add(course)

        count = student_loaded.courses.count()
        assert count == 3

    def test_many_to_many_iteration(self, db):
        """Test iterating over many-to-many relationship."""
        student = Student(student_id=1, name="Alice")
        student.save()

        Course(course_id=101, title="Math").save()
        Course(course_id=102, title="Science").save()

        student_loaded = Student.get(student_id=1)
        math = Course.get(course_id=101)
        science = Course.get(course_id=102)

        student_loaded.courses.add(math)
        student_loaded.courses.add(science)

        # Iterate using for loop
        course_titles = [course.title for course in student_loaded.courses]
        assert len(course_titles) == 2
        assert set(course_titles) == {"Math", "Science"}

    def test_many_to_many_len(self, db):
        """Test len() on many-to-many relationship."""
        student = Student(student_id=1, name="Alice")
        student.save()

        Course(course_id=101, title="Math").save()
        Course(course_id=102, title="Science").save()

        student_loaded = Student.get(student_id=1)
        math = Course.get(course_id=101)
        science = Course.get(course_id=102)

        student_loaded.courses.add(math)
        student_loaded.courses.add(science)

        assert len(student_loaded.courses) == 2


class TestManyToManyBidirectional:
    """Test bidirectional many-to-many relationships."""

    def test_bidirectional_navigation(self, db):
        """Test navigation in both directions."""
        # Create students and courses
        student1 = Student(student_id=1, name="Alice")
        student1.save()

        student2 = Student(student_id=2, name="Bob")
        student2.save()

        course = Course(course_id=101, title="Math")
        course.save()

        # Add from student side
        student1_loaded = Student.get(student_id=1)
        course_loaded = Course.get(course_id=101)
        student1_loaded.courses.add(course_loaded)

        # Add from course side
        student2_loaded = Student.get(student_id=2)
        course_loaded.students.add(student2_loaded)

        # Verify from student side
        student1_courses = student1_loaded.courses.all()
        assert len(student1_courses) == 1
        assert student1_courses[0].title == "Math"

        student2_courses = student2_loaded.courses.all()
        assert len(student2_courses) == 1
        assert student2_courses[0].title == "Math"

        # Verify from course side
        course_students = course_loaded.students.all()
        assert len(course_students) == 2
        student_names = {s.name for s in course_students}
        assert student_names == {"Alice", "Bob"}


class TestManyToManyManagement:
    """Test add/remove/clear methods."""

    def test_many_to_many_add(self, db):
        """Test adding relationships."""
        student = Student(student_id=1, name="Alice")
        student.save()

        course = Course(course_id=101, title="Math")
        course.save()

        student_loaded = Student.get(student_id=1)
        course_loaded = Course.get(course_id=101)

        # Add relationship
        student_loaded.courses.add(course_loaded)

        # Verify relationship exists
        courses = student_loaded.courses.all()
        assert len(courses) == 1
        assert courses[0].title == "Math"

    def test_many_to_many_add_duplicate(self, db):
        """Test adding same relationship twice (should be idempotent)."""
        student = Student(student_id=1, name="Alice")
        student.save()

        course = Course(course_id=101, title="Math")
        course.save()

        student_loaded = Student.get(student_id=1)
        course_loaded = Course.get(course_id=101)

        # Add twice
        student_loaded.courses.add(course_loaded)
        student_loaded.courses.add(course_loaded)

        # Should only have one enrollment
        assert len(student_loaded.courses) == 1

    def test_many_to_many_remove(self, db):
        """Test removing relationships."""
        student = Student(student_id=1, name="Alice")
        student.save()

        course = Course(course_id=101, title="Math")
        course.save()

        student_loaded = Student.get(student_id=1)
        course_loaded = Course.get(course_id=101)

        # Add then remove
        student_loaded.courses.add(course_loaded)
        assert len(student_loaded.courses) == 1

        student_loaded.courses.remove(course_loaded)

        # Verify relationship no longer exists
        student_reloaded = Student.get(student_id=1)
        assert len(student_reloaded.courses) == 0

    def test_many_to_many_clear(self, db):
        """Test clearing all relationships."""
        student = Student(student_id=1, name="Alice")
        student.save()

        # Create multiple courses
        Course(course_id=101, title="Math").save()
        Course(course_id=102, title="Science").save()
        Course(course_id=103, title="History").save()

        student_loaded = Student.get(student_id=1)
        for course_id in [101, 102, 103]:
            course = Course.get(course_id=course_id)
            student_loaded.courses.add(course)

        assert len(student_loaded.courses) == 3

        # Clear all
        student_loaded.courses.clear()

        # Verify all relationships removed
        student_reloaded = Student.get(student_id=1)
        assert len(student_reloaded.courses) == 0


class TestManyToManyJunctionTable:
    """Test junction table behavior."""

    def test_automatic_junction_table_creation(self, db):
        """Test that junction table is created automatically."""
        student = Student(student_id=1, name="Alice")
        student.save()

        course = Course(course_id=101, title="Math")
        course.save()

        # Access the manager to trigger junction table creation
        student_loaded = Student.get(student_id=1)
        _ = student_loaded.courses

        # Verify table exists
        cursor = db._connection.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='enrollments'"
        )
        result = cursor.fetchone()
        cursor.close()

        assert result is not None
        assert result[0] == "enrollments"

    def test_junction_table_schema(self, db):
        """Test that junction table has correct schema."""
        student = Student(student_id=1, name="Alice")
        student.save()

        # Trigger junction table creation
        _ = student.courses

        # Check table schema
        cursor = db._connection.cursor()
        cursor.execute("PRAGMA table_info(enrollments)")
        columns = cursor.fetchall()
        cursor.close()

        column_names = [col[1] for col in columns]
        assert "student_id" in column_names
        assert "course_id" in column_names


class TestManyToManyWithTransactions:
    """Test many-to-many behavior with transactions."""

    def test_many_to_many_in_transaction(self, db):
        """Test many-to-many works within transactions."""
        with db.transaction():
            student = Student(student_id=1, name="Alice")
            student.save()

            course1 = Course(course_id=101, title="Math")
            course1.save()

            course2 = Course(course_id=102, title="Science")
            course2.save()

            student.courses.add(course1)
            student.courses.add(course2)

        # Load after transaction
        student_loaded = Student.get(student_id=1)
        assert len(student_loaded.courses) == 2

    def test_many_to_many_rollback(self, db):
        """Test many-to-many relationships rolled back on error."""
        student = Student(student_id=1, name="Alice")
        student.save()

        course = Course(course_id=101, title="Math")
        course.save()

        # First check that no relationship exists
        student_check = Student.get(student_id=1)
        assert len(student_check.courses) == 0

        try:
            with db.transaction():
                student_check.courses.add(course)
                msg = "Simulated error"
                raise ValueError(msg)
        except ValueError:
            pass

        # Relationship should not exist after rollback
        student_loaded = Student.get(student_id=1)
        assert len(student_loaded.courses) == 0


class TestManyToManyPersistence:
    """Test many-to-many persistence across database sessions."""

    def test_many_to_many_persists(self, db_path):
        """Test many-to-many relationships persist across sessions."""
        # First session
        db1 = KenobiX(str(db_path))
        Document.set_database(db1)

        student = Student(student_id=1, name="Alice")
        student.save()

        Course(course_id=101, title="Math").save()
        Course(course_id=102, title="Science").save()

        math = Course.get(course_id=101)
        science = Course.get(course_id=102)

        student.courses.add(math)
        student.courses.add(science)

        db1.close()

        # Second session
        db2 = KenobiX(str(db_path))
        Document.set_database(db2)

        student_loaded = Student.get(student_id=1)
        assert student_loaded is not None
        courses = student_loaded.courses.all()
        assert len(courses) == 2
        course_titles = {c.title for c in courses}
        assert course_titles == {"Math", "Science"}

        db2.close()


class TestManyToManyDescriptor:
    """Test ManyToMany descriptor protocol."""

    def test_descriptor_class_access(self, db):
        """Test accessing ManyToMany on class returns descriptor."""
        descriptor = Student.courses
        assert isinstance(descriptor, ManyToMany)

    def test_descriptor_attributes(self, db):
        """Test ManyToMany descriptor attributes."""
        descriptor = Student.courses
        assert descriptor.related_model == Course
        assert descriptor.through == "enrollments"
        assert descriptor.local_field == "student_id"
        assert descriptor.remote_field == "course_id"

    def test_descriptor_prevents_direct_assignment(self, db):
        """Test that direct assignment to ManyToMany raises error."""
        student = Student(student_id=1, name="Alice")
        student.save()

        student_loaded = Student.get(student_id=1)

        # Attempting to assign directly should raise AttributeError
        with pytest.raises(
            AttributeError, match="Cannot directly assign to ManyToMany"
        ):
            student_loaded.courses = []  # type: ignore[misc]


class TestManyToManyEdgeCases:
    """Test edge cases and corner conditions."""

    def test_many_to_many_manager_caching(self, db):
        """Test that manager is cached per instance."""
        student = Student(student_id=1, name="Alice")
        student.save()

        student_loaded = Student.get(student_id=1)

        # Get manager twice
        manager1 = student_loaded.courses
        manager2 = student_loaded.courses

        # Should be same object (cached)
        assert manager1 is manager2

    def test_many_to_many_with_limit(self, db):
        """Test many-to-many with limit parameter."""
        student = Student(student_id=1, name="Alice")
        student.save()

        # Create many courses
        for i in range(150):
            Course(course_id=100 + i, title=f"Course {i}").save()

        student_loaded = Student.get(student_id=1)

        # Add all courses
        for i in range(150):
            course = Course.get(course_id=100 + i)
            student_loaded.courses.add(course)

        # Default limit is 100
        courses_default = student_loaded.courses.all()
        assert len(courses_default) == 100

        # Custom limit
        courses_limited = student_loaded.courses.all(limit=50)
        assert len(courses_limited) == 50

    def test_many_to_many_isolation(self, db):
        """Test that relationships are properly isolated."""
        # Create students
        student1 = Student(student_id=1, name="Alice")
        student1.save()

        student2 = Student(student_id=2, name="Bob")
        student2.save()

        # Create courses
        Course(course_id=101, title="Math").save()
        Course(course_id=102, title="Science").save()
        Course(course_id=103, title="History").save()

        # Student 1 enrolls in Math and Science
        student1_loaded = Student.get(student_id=1)
        math = Course.get(course_id=101)
        science = Course.get(course_id=102)
        student1_loaded.courses.add(math)
        student1_loaded.courses.add(science)

        # Student 2 enrolls in History
        student2_loaded = Student.get(student_id=2)
        history = Course.get(course_id=103)
        student2_loaded.courses.add(history)

        # Verify isolation
        assert len(student1_loaded.courses) == 2
        assert len(student2_loaded.courses) == 1

        # Verify correct courses
        student1_courses = {c.title for c in student1_loaded.courses.all()}
        assert student1_courses == {"Math", "Science"}

        student2_courses = {c.title for c in student2_loaded.courses.all()}
        assert student2_courses == {"History"}
