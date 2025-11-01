from typing import Any, Optional
import datetime
import decimal
import uuid

from pgvector.sqlalchemy.vector import VECTOR
from sqlalchemy import ARRAY, BigInteger, Boolean, CheckConstraint, DateTime, Double, Enum, ForeignKeyConstraint, Index, Integer, Numeric, PrimaryKeyConstraint, REAL, SmallInteger, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class Categories(Base):
    __tablename__ = 'categories'
    __table_args__ = (
    ForeignKeyConstraint(['parent_id'], ['public.categories.id'], ondelete='SET NULL', name='categories_parent_id_fkey'),
        PrimaryKeyConstraint('id', name='categories_pkey'),
        UniqueConstraint('slug', name='categories_slug_key'),
        Index('idx_categories_parent_order', 'parent_id', 'order_index'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    order_index: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    is_onboarding_visible: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('true'))

    parent: Mapped[Optional['Categories']] = relationship('Categories', remote_side=[id], back_populates='parent_reverse')
    parent_reverse: Mapped[list['Categories']] = relationship('Categories', remote_side=[parent_id], back_populates='parent')
    topics: Mapped[list['Topics']] = relationship('Topics', back_populates='category')
    courses: Mapped[list['Courses']] = relationship('Courses', back_populates='category')


class LearningFields(Base):
    __tablename__ = 'learning_fields'
    __table_args__ = (
    ForeignKeyConstraint(['parent_id'], ['public.learning_fields.id'], name='learning_fields_learning_fields_fk'),
        PrimaryKeyConstraint('id', name='learning_fields_pk'),
        {'schema': 'public'}
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    parent: Mapped[Optional['LearningFields']] = relationship('LearningFields', remote_side=[id], back_populates='parent_reverse')
    parent_reverse: Mapped[list['LearningFields']] = relationship('LearningFields', remote_side=[parent_id], back_populates='parent')


class Role(Base):
    __tablename__ = 'role'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='role_pk'),
        UniqueConstraint('role_name', name='role_unique'),
        {'schema': 'public'}
    )

    role_name: Mapped[str] = mapped_column(String, nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    user_roles: Mapped[list['UserRoles']] = relationship('UserRoles', back_populates='role')


class User(Base):
    __tablename__ = 'user'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='user_pk'),
        UniqueConstraint('email', name='user_unique'),
        {'schema': 'public'}
    )

    fullname: Mapped[str] = mapped_column(String, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    birthday: Mapped[Optional[str]] = mapped_column(String)
    conscious: Mapped[Optional[str]] = mapped_column(String)
    district: Mapped[Optional[str]] = mapped_column(String)
    citizenship_identity: Mapped[Optional[str]] = mapped_column(String)
    avatar: Mapped[Optional[str]] = mapped_column(String)
    bio: Mapped[Optional[str]] = mapped_column(Text)
    facebook_url: Mapped[Optional[str]] = mapped_column(String)
    is_verified_email: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    email_verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    create_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    update_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    preferences_str: Mapped[Optional[str]] = mapped_column(Text)
    preferences_embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(3072))
    preferences_embedding_date_updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    is_banned: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    banned_reason: Mapped[Optional[str]] = mapped_column(Text)
    banned_until: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    last_login_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    deleted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    deleted_until: Mapped[Optional[str]] = mapped_column(Text)
    course_count: Mapped[Optional[int]] = mapped_column(BigInteger, server_default=text('0'))
    rating_avg: Mapped[Optional[float]] = mapped_column(REAL, server_default=text('0'))
    student_count: Mapped[Optional[int]] = mapped_column(BigInteger, server_default=text('0'))
    instructor_description: Mapped[Optional[str]] = mapped_column(Text)
    evaluated_count: Mapped[Optional[int]] = mapped_column(BigInteger, server_default=text('0'))

    email_verifications: Mapped[list['EmailVerifications']] = relationship('EmailVerifications', back_populates='user')
    notifications: Mapped[list['Notifications']] = relationship('Notifications', back_populates='user')
    user_roles: Mapped[list['UserRoles']] = relationship('UserRoles', back_populates='user')
    wallets: Mapped[Optional['Wallets']] = relationship('Wallets', uselist=False, back_populates='user')
    courses: Mapped[list['Courses']] = relationship('Courses', foreign_keys='[Courses.approved_by]', back_populates='user')
    courses_: Mapped[list['Courses']] = relationship('Courses', foreign_keys='[Courses.instructor_id]', back_populates='instructor')
    course_enrollments: Mapped[list['CourseEnrollments']] = relationship('CourseEnrollments', back_populates='user')
    course_favourites: Mapped[list['CourseFavourites']] = relationship('CourseFavourites', back_populates='user')
    course_reviews: Mapped[list['CourseReviews']] = relationship('CourseReviews', back_populates='user')
    course_views: Mapped[list['CourseViews']] = relationship('CourseViews', back_populates='user')
    transactions: Mapped[list['Transactions']] = relationship('Transactions', back_populates='user')
    user_embedding_history: Mapped[list['UserEmbeddingHistory']] = relationship('UserEmbeddingHistory', back_populates='user')
    lecturer_upgrade_payments: Mapped[list['LecturerUpgradePayments']] = relationship('LecturerUpgradePayments', foreign_keys='[LecturerUpgradePayments.user_id]', back_populates='user')
    lecturer_upgrade_payments_: Mapped[list['LecturerUpgradePayments']] = relationship('LecturerUpgradePayments', foreign_keys='[LecturerUpgradePayments.verified_by]', back_populates='user_')
    lesson_active: Mapped[list['LessonActive']] = relationship('LessonActive', back_populates='user')
    lesson_progress: Mapped[list['LessonProgress']] = relationship('LessonProgress', back_populates='user')


class EmailVerifications(Base):
    __tablename__ = 'email_verifications'
    __table_args__ = (
    ForeignKeyConstraint(['user_id'], ['public.user.id'], name='email_verifications_user_fk'),
        PrimaryKeyConstraint('id', name='email_verifications_pk'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    code: Mapped[Optional[str]] = mapped_column(String)
    expired_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    user: Mapped[Optional['User']] = relationship('User', back_populates='email_verifications')


class Notifications(Base):
    __tablename__ = 'notifications'
    __table_args__ = (
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='notifications_user_id_fkey'),
        PrimaryKeyConstraint('id', name='notifications_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    role_target: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(Text)
    metadata_: Mapped[Optional[dict]] = mapped_column('metadata', JSONB, server_default=text("'{}'::jsonb"))
    is_read: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    read_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    is_clicked: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    clicked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    action: Mapped[Optional[str]] = mapped_column(String(50))

    user: Mapped['User'] = relationship('User', back_populates='notifications')


class Topics(Base):
    __tablename__ = 'topics'
    __table_args__ = (
    ForeignKeyConstraint(['category_id'], ['public.categories.id'], ondelete='CASCADE', name='topics_category_id_fkey'),
        PrimaryKeyConstraint('id', name='topics_pkey'),
        UniqueConstraint('slug', name='topics_slug_key'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    category_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    order_index: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('1'))
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('true'))
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(3072))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    category: Mapped['Categories'] = relationship('Categories', back_populates='topics')
    courses: Mapped[list['Courses']] = relationship('Courses', back_populates='topic')


class UserRoles(Base):
    __tablename__ = 'user_roles'
    __table_args__ = (
    ForeignKeyConstraint(['role_id'], ['public.role.id'], name='user_roles_role_fk'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], name='user_roles_user_fk'),
        PrimaryKeyConstraint('id', name='user_roles_pk'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    create_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    update_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    role_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    role: Mapped[Optional['Role']] = relationship('Role', back_populates='user_roles')
    user: Mapped[Optional['User']] = relationship('User', back_populates='user_roles')


class Wallets(Base):
    __tablename__ = 'wallets'
    __table_args__ = (
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='wallets_user_id_fkey'),
        PrimaryKeyConstraint('id', name='wallets_pkey'),
        UniqueConstraint('user_id', name='wallets_user_id_key'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    balance: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2), server_default=text('0'))
    total_in: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2), server_default=text('0'))
    total_out: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2), server_default=text('0'))
    last_transaction_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    user: Mapped[Optional['User']] = relationship('User', back_populates='wallets')


class Courses(Base):
    __tablename__ = 'courses'
    __table_args__ = (
        CheckConstraint("level = ANY (ARRAY['beginner'::text, 'intermediate'::text, 'advanced'::text, 'all'::text])", name='courses_level_check'),
    ForeignKeyConstraint(['approved_by'], ['public.user.id'], ondelete='SET NULL', name='courses_approved_by_fkey'),
    ForeignKeyConstraint(['category_id'], ['public.categories.id'], name='courses_categories_fk'),
    ForeignKeyConstraint(['instructor_id'], ['public.user.id'], name='courses_user_fk'),
    ForeignKeyConstraint(['topic_id'], ['public.topics.id'], ondelete='SET NULL', name='courses_topic_id_fkey'),
        PrimaryKeyConstraint('id', name='courses_pkey'),
        UniqueConstraint('slug', name='courses_slug_key'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    instructor_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    is_lock_lesson: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    subtitle: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    level: Mapped[Optional[str]] = mapped_column(Text, server_default=text("'all'::text"))
    language: Mapped[Optional[str]] = mapped_column(Text, server_default=text("'vi'::text"))
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text)
    promo_video_url: Mapped[Optional[str]] = mapped_column(Text)
    total_length_seconds: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    is_published: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    rating_avg: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(3, 2), server_default=text('0.00'))
    rating_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    search_tsv: Mapped[Optional[Any]] = mapped_column(TSVECTOR)
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(3072))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    deleted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    outcomes: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    base_price: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2), server_default=text('0.00'))
    currency: Mapped[Optional[str]] = mapped_column(String(10), server_default=text("'VND'::character varying"))
    requirements: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    target_audience: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    embedding_updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    views: Mapped[Optional[int]] = mapped_column(BigInteger, server_default=text('0'))
    total_enrolls: Mapped[Optional[int]] = mapped_column(BigInteger, server_default=text('0'))
    total_reviews: Mapped[Optional[int]] = mapped_column(BigInteger, server_default=text('0'))
    approval_note: Mapped[Optional[str]] = mapped_column(Text)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    approved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    review_round: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('1'))
    approval_status: Mapped[Optional[str]] = mapped_column(String, server_default=text("'pending'::character varying"))
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    user: Mapped[Optional['User']] = relationship('User', foreign_keys=[approved_by], back_populates='courses')
    category: Mapped[Optional['Categories']] = relationship('Categories', back_populates='courses')
    instructor: Mapped['User'] = relationship('User', foreign_keys=[instructor_id], back_populates='courses_')
    topic: Mapped[Optional['Topics']] = relationship('Topics', back_populates='courses')
    course_enrollments: Mapped[list['CourseEnrollments']] = relationship('CourseEnrollments', back_populates='course')
    course_favourites: Mapped[list['CourseFavourites']] = relationship('CourseFavourites', back_populates='course')
    course_reviews: Mapped[list['CourseReviews']] = relationship('CourseReviews', back_populates='course')
    course_sections: Mapped[list['CourseSections']] = relationship('CourseSections', back_populates='course')
    course_views: Mapped[list['CourseViews']] = relationship('CourseViews', back_populates='course')
    transactions: Mapped[list['Transactions']] = relationship('Transactions', back_populates='course')
    user_embedding_history: Mapped[list['UserEmbeddingHistory']] = relationship('UserEmbeddingHistory', back_populates='course')
    lessons: Mapped[list['Lessons']] = relationship('Lessons', back_populates='course')
    lesson_active: Mapped[list['LessonActive']] = relationship('LessonActive', back_populates='course')
    lesson_progress: Mapped[list['LessonProgress']] = relationship('LessonProgress', back_populates='course')
    lesson_quizzes: Mapped[list['LessonQuizzes']] = relationship('LessonQuizzes', back_populates='course')


class CourseEnrollments(Base):
    __tablename__ = 'course_enrollments'
    __table_args__ = (
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], ondelete='CASCADE', name='course_enrollments_course_id_fkey'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='course_enrollments_user_id_fkey'),
        PrimaryKeyConstraint('id', name='course_enrollments_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    course_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    enrolled_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    progress: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 2), server_default=text('0'))
    last_accessed: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    status: Mapped[Optional[str]] = mapped_column(Text, server_default=text("'active'::text"))

    course: Mapped[Optional['Courses']] = relationship('Courses', back_populates='course_enrollments')
    user: Mapped[Optional['User']] = relationship('User', back_populates='course_enrollments')


class CourseFavourites(Base):
    __tablename__ = 'course_favourites'
    __table_args__ = (
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], ondelete='CASCADE', name='course_favourites_course_id_fkey'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='course_favourites_user_id_fkey'),
        PrimaryKeyConstraint('course_id', 'user_id', name='course_favourites_pk'),
        {'schema': 'public'}
    )

    course_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    course: Mapped['Courses'] = relationship('Courses', back_populates='course_favourites')
    user: Mapped['User'] = relationship('User', back_populates='course_favourites')


class CourseReviews(Base):
    __tablename__ = 'course_reviews'
    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 5', name='course_reviews_rating_check'),
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], ondelete='CASCADE', name='course_reviews_course_id_fkey'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='course_reviews_user_id_fkey'),
        PrimaryKeyConstraint('id', name='course_reviews_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    course_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger)
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(3072))
    sentiment: Mapped[Optional[str]] = mapped_column(String(20))
    topics: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    course: Mapped[Optional['Courses']] = relationship('Courses', back_populates='course_reviews')
    user: Mapped[Optional['User']] = relationship('User', back_populates='course_reviews')


class CourseSections(Base):
    __tablename__ = 'course_sections'
    __table_args__ = (
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], ondelete='CASCADE', name='course_sections_course_id_fkey'),
        PrimaryKeyConstraint('id', name='course_sections_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    course_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    course: Mapped[Optional['Courses']] = relationship('Courses', back_populates='course_sections')
    lessons: Mapped[list['Lessons']] = relationship('Lessons', back_populates='section')
    lesson_quizzes: Mapped[list['LessonQuizzes']] = relationship('LessonQuizzes', back_populates='section')


class CourseViews(Base):
    __tablename__ = 'course_views'
    __table_args__ = (
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], ondelete='CASCADE', name='course_views_course_id_fkey'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='course_views_user_id_fkey'),
        PrimaryKeyConstraint('id', name='course_views_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    course_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    course: Mapped[Optional['Courses']] = relationship('Courses', back_populates='course_views')
    user: Mapped[Optional['User']] = relationship('User', back_populates='course_views')


class Transactions(Base):
    __tablename__ = 'transactions'
    __table_args__ = (
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], name='transactions_courses_fk'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='transactions_user_id_fkey'),
        PrimaryKeyConstraint('id', name='transactions_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    currency: Mapped[Optional[str]] = mapped_column(String(10), server_default=text("'VND'::character varying"))
    method: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'pending'::character varying"))
    transaction_code: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    confirmed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    course_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    course: Mapped[Optional['Courses']] = relationship('Courses', back_populates='transactions')
    user: Mapped[Optional['User']] = relationship('User', back_populates='transactions')
    lecturer_upgrade_payments: Mapped[list['LecturerUpgradePayments']] = relationship('LecturerUpgradePayments', back_populates='transaction')


class UserEmbeddingHistory(Base):
    __tablename__ = 'user_embedding_history'
    __table_args__ = (
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], ondelete='CASCADE', name='user_embedding_history_course_id_fkey'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='user_embedding_history_user_id_fkey'),
        PrimaryKeyConstraint('id', name='user_embedding_history_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    interaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(3072))
    lambda_: Mapped[Optional[float]] = mapped_column(Double(53))
    similarity: Mapped[Optional[float]] = mapped_column(Double(53))
    decay: Mapped[Optional[float]] = mapped_column(Double(53))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    course: Mapped['Courses'] = relationship('Courses', back_populates='user_embedding_history')
    user: Mapped['User'] = relationship('User', back_populates='user_embedding_history')


class LecturerUpgradePayments(Base):
    __tablename__ = 'lecturer_upgrade_payments'
    __table_args__ = (
    ForeignKeyConstraint(['transaction_id'], ['public.transactions.id'], ondelete='SET NULL', name='lecturer_upgrade_payments_transaction_id_fkey'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='lecturer_upgrade_payments_user_id_fkey'),
    ForeignKeyConstraint(['verified_by'], ['public.user.id'], name='lecturer_upgrade_payments_verified_by_fkey'),
        PrimaryKeyConstraint('id', name='lecturer_upgrade_payments_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    payment_status: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'pending'::character varying"))
    paid_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    verified_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    transaction: Mapped[Optional['Transactions']] = relationship('Transactions', back_populates='lecturer_upgrade_payments')
    user: Mapped['User'] = relationship('User', foreign_keys=[user_id], back_populates='lecturer_upgrade_payments')
    user_: Mapped[Optional['User']] = relationship('User', foreign_keys=[verified_by], back_populates='lecturer_upgrade_payments_')


class Lessons(Base):
    __tablename__ = 'lessons'
    __table_args__ = (
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], name='lessons_courses_fk'),
    ForeignKeyConstraint(['section_id'], ['public.course_sections.id'], ondelete='CASCADE', name='lessons_section_id_fkey'),
        PrimaryKeyConstraint('id', name='lessons_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    lesson_type: Mapped[str] = mapped_column(Enum('video', 'article', 'quiz', 'coding', 'assignment', 'resource', name='lesson_type_enum'), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    section_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    description: Mapped[Optional[str]] = mapped_column(Text)
    prerequisites: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    outcomes: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    is_preview: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(3072))
    content_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    course_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    course: Mapped[Optional['Courses']] = relationship('Courses', back_populates='lessons')
    section: Mapped[Optional['CourseSections']] = relationship('CourseSections', back_populates='lessons')
    lesson_active: Mapped[list['LessonActive']] = relationship('LessonActive', back_populates='lesson')
    lesson_chunks: Mapped[list['LessonChunks']] = relationship('LessonChunks', back_populates='lesson')
    lesson_progress: Mapped[list['LessonProgress']] = relationship('LessonProgress', back_populates='lesson')
    lesson_quizzes: Mapped[list['LessonQuizzes']] = relationship('LessonQuizzes', back_populates='lesson')
    lesson_resources: Mapped[list['LessonResources']] = relationship('LessonResources', back_populates='lesson')
    # 🧩 Auto relationship (parent → child): LessonVideos
    lesson_videos: Mapped[Optional['LessonVideos']] = relationship(
        'LessonVideos', back_populates='lessons', uselist=False)


class LessonActive(Base):
    __tablename__ = 'lesson_active'
    __table_args__ = (
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], ondelete='CASCADE', name='lesson_active_course_fk'),
    ForeignKeyConstraint(['lesson_id'], ['public.lessons.id'], ondelete='CASCADE', name='lesson_active_lesson_fk'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='lesson_active_user_fk'),
        PrimaryKeyConstraint('user_id', 'course_id', name='lesson_active_pk'),
        {'schema': 'public'}
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    course_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    activated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    course: Mapped['Courses'] = relationship('Courses', back_populates='lesson_active')
    lesson: Mapped['Lessons'] = relationship('Lessons', back_populates='lesson_active')
    user: Mapped['User'] = relationship('User', back_populates='lesson_active')


class LessonChunks(Base):
    __tablename__ = 'lesson_chunks'
    __table_args__ = (
    ForeignKeyConstraint(['lesson_id'], ['public.lessons.id'], ondelete='CASCADE', name='lesson_chunks_lesson_id_fkey'),
        PrimaryKeyConstraint('id', name='lesson_chunks_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    lesson_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    chunk_index: Mapped[Optional[int]] = mapped_column(Integer)
    text_: Mapped[Optional[str]] = mapped_column('text', Text)
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(3072))
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    lesson: Mapped[Optional['Lessons']] = relationship('Lessons', back_populates='lesson_chunks')


class LessonProgress(Base):
    __tablename__ = 'lesson_progress'
    __table_args__ = (
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], ondelete='CASCADE', name='lesson_progress_course_id_fkey'),
    ForeignKeyConstraint(['lesson_id'], ['public.lessons.id'], ondelete='CASCADE', name='lesson_progress_lesson_id_fkey'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='lesson_progress_user_id_fkey'),
        PrimaryKeyConstraint('id', name='lesson_progress_pkey'),
        UniqueConstraint('user_id', 'lesson_id', name='lesson_progress_unique'),
        Index('idx_lesson_progress_user_course', 'user_id', 'course_id'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    lesson_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    is_completed: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    course: Mapped['Courses'] = relationship('Courses', back_populates='lesson_progress')
    lesson: Mapped['Lessons'] = relationship('Lessons', back_populates='lesson_progress')
    user: Mapped['User'] = relationship('User', back_populates='lesson_progress')


class LessonQuizzes(Base):
    __tablename__ = 'lesson_quizzes'
    __table_args__ = (
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], ondelete='CASCADE', name='lesson_quizzes_course_id_fkey'),
    ForeignKeyConstraint(['lesson_id'], ['public.lessons.id'], ondelete='CASCADE', name='lesson_quizzes_lesson_id_fkey'),
    ForeignKeyConstraint(['section_id'], ['public.course_sections.id'], ondelete='CASCADE', name='lesson_quizzes_section_id_fkey'),
        PrimaryKeyConstraint('id', name='lesson_quizzes_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    lesson_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    section_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    course_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    difficulty_level: Mapped[Optional[int]] = mapped_column(SmallInteger, server_default=text('1'))
    created_by: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'ai'::character varying"))
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(3072))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    course: Mapped[Optional['Courses']] = relationship('Courses', back_populates='lesson_quizzes')
    lesson: Mapped[Optional['Lessons']] = relationship('Lessons', back_populates='lesson_quizzes')
    section: Mapped[Optional['CourseSections']] = relationship('CourseSections', back_populates='lesson_quizzes')
    lesson_quiz_options: Mapped[list['LessonQuizOptions']] = relationship('LessonQuizOptions', back_populates='quiz')


class LessonResources(Base):
    __tablename__ = 'lesson_resources'
    __table_args__ = (
    ForeignKeyConstraint(['lesson_id'], ['public.lessons.id'], ondelete='CASCADE', name='lesson_resources_lesson_id_fkey'),
        PrimaryKeyConstraint('id', name='lesson_resources_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    lesson_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    resource_type: Mapped[Optional[str]] = mapped_column(Text)
    title: Mapped[Optional[str]] = mapped_column(String)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger)
    mime_type: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    lesson: Mapped[Optional['Lessons']] = relationship('Lessons', back_populates='lesson_resources')


class LessonVideos(Base):
    __tablename__ = 'lesson_videos'
    __table_args__ = (
    ForeignKeyConstraint(['lesson_id'], ['public.lessons.id'], name='lesson_videos_lessons_fk'),
        PrimaryKeyConstraint('lesson_id', name='lesson_videos_pkey'),
        {'schema': 'public'}
    )

    lesson_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    video_url: Mapped[str] = mapped_column(Text, nullable=False)
    transcript: Mapped[Optional[str]] = mapped_column(Text)
    duration: Mapped[Optional[float]] = mapped_column(Double(53), server_default=text('0'))
    file_id: Mapped[Optional[str]] = mapped_column(String)
    # 🧩 Auto relationship (child → parent): Lessons
    lessons: Mapped['Lessons'] = relationship(
        'Lessons', back_populates='lesson_videos', uselist=False)


class LessonQuizOptions(Base):
    __tablename__ = 'lesson_quiz_options'
    __table_args__ = (
    ForeignKeyConstraint(['quiz_id'], ['public.lesson_quizzes.id'], ondelete='CASCADE', name='lesson_quiz_options_quiz_id_fkey'),
        PrimaryKeyConstraint('id', name='lesson_quiz_options_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    text_: Mapped[str] = mapped_column('text', Text, nullable=False)
    quiz_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    position: Mapped[Optional[int]] = mapped_column(SmallInteger, server_default=text('1'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    quiz: Mapped[Optional['LessonQuizzes']] = relationship('LessonQuizzes', back_populates='lesson_quiz_options')


# === AUTO FIX SUMMARY ===
# • Đã đổi class kế thừa (trừ Base) → Base.
# • Đã thêm relationship() 1–1 hai chiều tự động (không trùng lặp).
# • Field dùng snake_case (vd: lesson_videos, course_reviews, ...).
# =========================
