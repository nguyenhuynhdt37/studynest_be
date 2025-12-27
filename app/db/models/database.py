from typing import Any, Optional
import datetime
import decimal
import uuid

from pgvector.sqlalchemy.vector import VECTOR
from sqlalchemy import ARRAY, BigInteger, Boolean, CheckConstraint, Computed, DateTime, Double, Enum, ForeignKeyConstraint, Index, Integer, Numeric, PrimaryKeyConstraint, REAL, SmallInteger, String, Text, UniqueConstraint, Uuid, text
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
    discount_targets: Mapped[list['DiscountTargets']] = relationship('DiscountTargets', back_populates='category')


class PlatformWallets(Base):
    __tablename__ = 'platform_wallets'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='platform_wallets_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    balance: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text('0'))
    total_in: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text('0'))
    total_out: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text('0'))
    holding_amount: Mapped[decimal.Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default=text('0'))
    platform_fee_total: Mapped[decimal.Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default=text('0'))
    currency: Mapped[Optional[str]] = mapped_column(Text, server_default=text("'VND'::text"))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    last_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    platform_wallet_history: Mapped[list['PlatformWalletHistory']] = relationship('PlatformWalletHistory', back_populates='wallet')


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


class SupportedLanguages(Base):
    __tablename__ = 'supported_languages'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='supported_languages_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[Optional[str]] = mapped_column(Text)
    aliases: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    runtime: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('true'))
    last_sync: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    lesson_codes: Mapped[list['LessonCodes']] = relationship('LessonCodes', back_populates='language')


class User(Base):
    __tablename__ = 'user'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='user_pk'),
        UniqueConstraint('email', name='user_unique'),
        Index('user_embedding_idx', 'preferences_embedding'),
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
    preferences_embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(1536))
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
    paypal_email: Mapped[Optional[str]] = mapped_column(String)
    paypal_payer_id: Mapped[Optional[str]] = mapped_column(String)

    discounts: Mapped[list['Discounts']] = relationship('Discounts', back_populates='user')
    email_verifications: Mapped[list['EmailVerifications']] = relationship('EmailVerifications', back_populates='user')
    notifications: Mapped[list['Notifications']] = relationship('Notifications', back_populates='user')
    platform_settings: Mapped[list['PlatformSettings']] = relationship('PlatformSettings', back_populates='user')
    user_roles: Mapped[list['UserRoles']] = relationship('UserRoles', back_populates='user')
    wallets: Mapped['Wallets'] = relationship('Wallets', uselist=False, back_populates='user')
    courses: Mapped[list['Courses']] = relationship('Courses', foreign_keys='[Courses.approved_by]', back_populates='user')
    courses_: Mapped[list['Courses']] = relationship('Courses', foreign_keys='[Courses.instructor_id]', back_populates='instructor')
    course_enrollments: Mapped[list['CourseEnrollments']] = relationship('CourseEnrollments', back_populates='user')
    course_favourites: Mapped[list['CourseFavourites']] = relationship('CourseFavourites', back_populates='user')
    course_reviews: Mapped[list['CourseReviews']] = relationship('CourseReviews', back_populates='user')
    course_views: Mapped[list['CourseViews']] = relationship('CourseViews', back_populates='user')
    transactions: Mapped[list['Transactions']] = relationship('Transactions', back_populates='user')
    user_embedding_history: Mapped[list['UserEmbeddingHistory']] = relationship('UserEmbeddingHistory', back_populates='user')
    instructor_earnings: Mapped[list['InstructorEarnings']] = relationship('InstructorEarnings', back_populates='instructor')
    purchase_items: Mapped[list['PurchaseItems']] = relationship('PurchaseItems', back_populates='user')
    withdrawal_requests: Mapped[list['WithdrawalRequests']] = relationship('WithdrawalRequests', back_populates='lecturer')
    discount_history: Mapped[list['DiscountHistory']] = relationship('DiscountHistory', back_populates='user')
    lesson_active: Mapped[list['LessonActive']] = relationship('LessonActive', back_populates='user')
    lesson_comments: Mapped[list['LessonComments']] = relationship('LessonComments', back_populates='user')
    lesson_notes: Mapped[list['LessonNotes']] = relationship('LessonNotes', back_populates='user')
    lesson_progress: Mapped[list['LessonProgress']] = relationship('LessonProgress', back_populates='user')
    lesson_tutor_memory: Mapped[list['LessonTutorMemory']] = relationship('LessonTutorMemory', back_populates='user')
    refund_requests: Mapped[list['RefundRequests']] = relationship('RefundRequests', foreign_keys='[RefundRequests.instructor_id]', back_populates='instructor')
    refund_requests_: Mapped[list['RefundRequests']] = relationship('RefundRequests', foreign_keys='[RefundRequests.resolved_by]', back_populates='user')
    refund_requests1: Mapped[list['RefundRequests']] = relationship('RefundRequests', foreign_keys='[RefundRequests.user_id]', back_populates='user_')
    tutor_chat_threads: Mapped[list['TutorChatThreads']] = relationship('TutorChatThreads', back_populates='user')
    lesson_comment_reactions: Mapped[list['LessonCommentReactions']] = relationship('LessonCommentReactions', back_populates='user')
    tutor_chat_messages: Mapped[list['TutorChatMessages']] = relationship('TutorChatMessages', back_populates='user')
    tutor_chat_images: Mapped[list['TutorChatImages']] = relationship('TutorChatImages', back_populates='user')


class Discounts(Base):
    __tablename__ = 'discounts'
    __table_args__ = (
        CheckConstraint("applies_to = ANY (ARRAY['global'::text, 'course'::text, 'category'::text, 'specific'::text])", name='discounts_applies_to_check'),
        CheckConstraint("created_role = ANY (ARRAY['ADMIN'::text, 'LECTURER'::text])", name='discounts_created_role_check'),
        CheckConstraint("discount_type = ANY (ARRAY['percent'::text, 'fixed'::text])", name='discounts_discount_type_check'),
    ForeignKeyConstraint(['created_by'], ['public.user.id'], name='discounts_created_by_fkey'),
        PrimaryKeyConstraint('id', name='discounts_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_role: Mapped[str] = mapped_column(Text, nullable=False)
    applies_to: Mapped[str] = mapped_column(Text, nullable=False)
    discount_type: Mapped[str] = mapped_column(Text, nullable=False)
    start_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    discount_code: Mapped[Optional[str]] = mapped_column(Text)
    is_hidden: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    percent_value: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 2))
    fixed_value: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2))
    usage_limit: Mapped[Optional[int]] = mapped_column(Integer)
    usage_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    per_user_limit: Mapped[Optional[int]] = mapped_column(Integer)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('true'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    user: Mapped['User'] = relationship('User', back_populates='discounts')
    discount_targets: Mapped[list['DiscountTargets']] = relationship('DiscountTargets', back_populates='discount')
    purchase_items: Mapped[list['PurchaseItems']] = relationship('PurchaseItems', back_populates='discount')
    discount_history: Mapped[list['DiscountHistory']] = relationship('DiscountHistory', back_populates='discount')


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
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    content: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(Text)
    metadata_: Mapped[Optional[dict]] = mapped_column('metadata', JSONB, server_default=text("'{}'::jsonb"))
    is_read: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    read_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    action: Mapped[Optional[str]] = mapped_column(String(50))
    role_target: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()), server_default=text("'{}'::text[]"))

    user: Mapped[Optional['User']] = relationship('User', back_populates='notifications')


class PlatformSettings(Base):
    __tablename__ = 'platform_settings'
    __table_args__ = (
    ForeignKeyConstraint(['updated_by'], ['public.user.id'], name='platform_settings_updated_by_fkey'),
        PrimaryKeyConstraint('id', name='platform_settings_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    platform_fee: Mapped[decimal.Decimal] = mapped_column(Numeric(5, 4), nullable=False, server_default=text('0.3000'))
    hold_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('7'))
    payout_min_balance: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text('100000'))
    payout_schedule: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'mon-wed-fri'::character varying"))
    currency: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'VND'::character varying"))
    allow_wallet_topup: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    allow_auto_withdraw: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    max_discounts_per_course: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('2'))
    discount_max_percent: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('90'))
    discount_min_price: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text('1000'))
    course_min_price: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text('10000'))
    course_max_price: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text('20000000'))
    course_default_language: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'vi'::character varying"))
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('3072'))
    search_top_k: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('8'))
    rag_max_chunks: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('50'))
    max_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('5'))
    lock_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('15'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text('now()'))
    instructor_fee: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 4), Computed('((1)::numeric - platform_fee)', persisted=True))
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    user: Mapped[Optional['User']] = relationship('User', back_populates='platform_settings')


class PlatformWalletHistory(Base):
    __tablename__ = 'platform_wallet_history'
    __table_args__ = (
        CheckConstraint("type = ANY (ARRAY['in'::text, 'out'::text, 'hold'::text, 'release'::text, 'fee'::text])", name='platform_wallet_history_type_check'),
    ForeignKeyConstraint(['wallet_id'], ['public.platform_wallets.id'], ondelete='CASCADE', name='platform_wallet_history_wallet_id_fkey'),
        PrimaryKeyConstraint('id', name='platform_wallet_history_pkey'),
        Index('idx_platform_wallet_history_created_at', 'created_at'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    wallet_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    related_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    note: Mapped[Optional[str]] = mapped_column(Text)

    wallet: Mapped['PlatformWallets'] = relationship('PlatformWallets', back_populates='platform_wallet_history')


class Topics(Base):
    __tablename__ = 'topics'
    __table_args__ = (
    ForeignKeyConstraint(['category_id'], ['public.categories.id'], ondelete='CASCADE', name='topics_category_id_fkey'),
        PrimaryKeyConstraint('id', name='topics_pkey'),
        UniqueConstraint('slug', name='topics_slug_key'),
        Index('topics_embedding_idx', 'embedding'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    category_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    order_index: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('1'))
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('true'))
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(1536))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    category: Mapped['Categories'] = relationship('Categories', back_populates='topics')
    courses: Mapped[list['Courses']] = relationship('Courses', back_populates='topic')


class UserRoles(Base):
    __tablename__ = 'user_roles'
    __table_args__ = (
    ForeignKeyConstraint(['role_id'], ['public.role.id'], name='user_roles_role_fk'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='user_roles_user_fk'),
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
        {'comment': 'Ví người dùng (1 user = 1 ví)', 'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    balance: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2), server_default=text('0'), comment='Số dư hiện tại của ví')
    total_in: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2), server_default=text('0'), comment='Tổng tiền nạp vào')
    total_out: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2), server_default=text('0'), comment='Tổng tiền rút ra')
    currency: Mapped[Optional[str]] = mapped_column(String(10), server_default=text("'VND'::character varying"), comment='Đơn vị tiền tệ (VND/USD)')
    is_locked: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'), comment='Khóa ví khi nghi ngờ gian lận')
    last_transaction_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    kyc_verified: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))

    user: Mapped['User'] = relationship('User', back_populates='wallets')


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
        Index('courses_embedding_idx', 'embedding'),
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
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(1536))
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
    discount_targets: Mapped[list['DiscountTargets']] = relationship('DiscountTargets', back_populates='course')
    transactions: Mapped[list['Transactions']] = relationship('Transactions', back_populates='course')
    user_embedding_history: Mapped[list['UserEmbeddingHistory']] = relationship('UserEmbeddingHistory', back_populates='course')
    lessons: Mapped[list['Lessons']] = relationship('Lessons', back_populates='course')
    purchase_items: Mapped[list['PurchaseItems']] = relationship('PurchaseItems', back_populates='course')
    lesson_active: Mapped[list['LessonActive']] = relationship('LessonActive', back_populates='course')
    lesson_progress: Mapped[list['LessonProgress']] = relationship('LessonProgress', back_populates='course')
    lesson_quizzes: Mapped[list['LessonQuizzes']] = relationship('LessonQuizzes', back_populates='course')
    tutor_chat_threads: Mapped[list['TutorChatThreads']] = relationship('TutorChatThreads', back_populates='course')


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
        Index('course_reviews_embedding_idx', 'embedding'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    course_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger)
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(1536))
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


class DiscountTargets(Base):
    __tablename__ = 'discount_targets'
    __table_args__ = (
        CheckConstraint('course_id IS NOT NULL OR category_id IS NOT NULL', name='discount_targets_check'),
    ForeignKeyConstraint(['category_id'], ['public.categories.id'], ondelete='CASCADE', name='discount_targets_category_id_fkey'),
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], ondelete='CASCADE', name='discount_targets_course_id_fkey'),
    ForeignKeyConstraint(['discount_id'], ['public.discounts.id'], ondelete='CASCADE', name='discount_targets_discount_id_fkey'),
        PrimaryKeyConstraint('id', name='discount_targets_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    discount_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    course_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    category: Mapped[Optional['Categories']] = relationship('Categories', back_populates='discount_targets')
    course: Mapped[Optional['Courses']] = relationship('Courses', back_populates='discount_targets')
    discount: Mapped['Discounts'] = relationship('Discounts', back_populates='discount_targets')


class Transactions(Base):
    __tablename__ = 'transactions'
    __table_args__ = (
        CheckConstraint('amount > 0::numeric', name='transactions_amount_positive'),
        CheckConstraint('amount > 0::numeric', name='transactions_amount_check'),
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], name='transactions_courses_fk'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='transactions_user_id_fkey'),
        PrimaryKeyConstraint('id', name='transactions_pkey'),
        Index('idx_transactions_user_date', 'user_id', 'created_at'),
        {'comment': 'Lịch sử giao dịch (mua khóa học, rút ví, thanh toán...)',
     'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    course_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    ref_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, comment='Liên kết đến bảng khác (purchases, lecturer_upgrade_payments)')
    currency: Mapped[Optional[str]] = mapped_column(String(10), server_default=text("'VND'::character varying"))
    direction: Mapped[Optional[str]] = mapped_column(String(10), server_default=text("'in'::character varying"), comment='in = nạp, out = rút')
    method: Mapped[Optional[str]] = mapped_column(String(50))
    gateway: Mapped[Optional[str]] = mapped_column(String(20), comment='Cổng thanh toán: PayPal, MoMo...')
    order_id: Mapped[Optional[str]] = mapped_column(String(100), comment='Mã đơn hàng từ PayPal/MoMo')
    status: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'pending'::character varying"), comment='pending / completed / failed / refunded')
    transaction_code: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    confirmed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    return_pathname: Mapped[Optional[str]] = mapped_column(Text)
    return_origin: Mapped[Optional[str]] = mapped_column(Text)

    course: Mapped[Optional['Courses']] = relationship('Courses', back_populates='transactions')
    user: Mapped['User'] = relationship('User', back_populates='transactions')
    instructor_earnings: Mapped[list['InstructorEarnings']] = relationship('InstructorEarnings', back_populates='transaction')
    purchase_items: Mapped[list['PurchaseItems']] = relationship('PurchaseItems', back_populates='transaction')
    withdrawal_requests: Mapped[list['WithdrawalRequests']] = relationship('WithdrawalRequests', back_populates='transaction')


class UserEmbeddingHistory(Base):
    __tablename__ = 'user_embedding_history'
    __table_args__ = (
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], ondelete='CASCADE', name='user_embedding_history_course_id_fkey'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='user_embedding_history_user_id_fkey'),
        PrimaryKeyConstraint('id', name='user_embedding_history_pkey'),
        Index('user_embedding_history_idx', 'embedding'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    interaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(1536))
    lambda_: Mapped[Optional[float]] = mapped_column(Double(53))
    similarity: Mapped[Optional[float]] = mapped_column(Double(53))
    decay: Mapped[Optional[float]] = mapped_column(Double(53))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    course: Mapped['Courses'] = relationship('Courses', back_populates='user_embedding_history')
    user: Mapped['User'] = relationship('User', back_populates='user_embedding_history')


class InstructorEarnings(Base):
    __tablename__ = 'instructor_earnings'
    __table_args__ = (
        CheckConstraint("status::text = ANY (ARRAY['holding'::character varying::text, 'pending'::character varying::text, 'paid'::character varying::text, 'refunded'::character varying::text])", name='instructor_earnings_status_check'),
    ForeignKeyConstraint(['instructor_id'], ['public.user.id'], ondelete='CASCADE', name='instructor_earnings_instructor_id_fkey'),
    ForeignKeyConstraint(['transaction_id'], ['public.transactions.id'], ondelete='CASCADE', name='instructor_earnings_transaction_id_fkey'),
        PrimaryKeyConstraint('id', name='instructor_earnings_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    transaction_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    instructor_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    amount_instructor: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_platform: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'holding'::character varying"))
    hold_until: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    available_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    paid_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    payout_reference: Mapped[Optional[str]] = mapped_column(String(100))
    purchase_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    instructor: Mapped['User'] = relationship('User', back_populates='instructor_earnings')
    transaction: Mapped['Transactions'] = relationship('Transactions', back_populates='instructor_earnings')


class Lessons(Base):
    __tablename__ = 'lessons'
    __table_args__ = (
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], name='lessons_courses_fk'),
    ForeignKeyConstraint(['section_id'], ['public.course_sections.id'], ondelete='CASCADE', name='lessons_section_id_fkey'),
        PrimaryKeyConstraint('id', name='lessons_pkey'),
        Index('lessons_embedding_idx', 'embedding'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    lesson_type: Mapped[str] = mapped_column(Enum('video', 'article', 'quiz', 'code', 'assignment', 'resource', name='lesson_type_enum'), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    section_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    description: Mapped[Optional[str]] = mapped_column(Text)
    prerequisites: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    outcomes: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    is_preview: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(1536))
    content_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    course_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    course: Mapped[Optional['Courses']] = relationship('Courses', back_populates='lessons')
    section: Mapped[Optional['CourseSections']] = relationship('CourseSections', back_populates='lessons')
    lesson_active: Mapped[list['LessonActive']] = relationship('LessonActive', back_populates='lesson')
    lesson_chunks: Mapped[list['LessonChunks']] = relationship('LessonChunks', back_populates='lesson')
    lesson_codes: Mapped[list['LessonCodes']] = relationship('LessonCodes', back_populates='lesson')
    lesson_comments: Mapped[list['LessonComments']] = relationship('LessonComments', back_populates='lesson')
    lesson_notes: Mapped[list['LessonNotes']] = relationship('LessonNotes', back_populates='lesson')
    lesson_progress: Mapped[list['LessonProgress']] = relationship('LessonProgress', back_populates='lesson')
    lesson_quizzes: Mapped[list['LessonQuizzes']] = relationship('LessonQuizzes', back_populates='lesson')
    lesson_resources: Mapped[list['LessonResources']] = relationship('LessonResources', back_populates='lesson')
    lesson_tutor_memory: Mapped[list['LessonTutorMemory']] = relationship('LessonTutorMemory', back_populates='lesson')
    tutor_chat_threads: Mapped[list['TutorChatThreads']] = relationship('TutorChatThreads', back_populates='lesson')
    resource_chunks: Mapped[list['ResourceChunks']] = relationship('ResourceChunks', back_populates='lesson')
    # 🧩 Auto relationship (parent → child): LessonVideos
    lesson_videos: Mapped[Optional['LessonVideos']] = relationship(
        'LessonVideos', back_populates='lessons', uselist=False)


class PurchaseItems(Base):
    __tablename__ = 'purchase_items'
    __table_args__ = (
        CheckConstraint("status = ANY (ARRAY['completed'::text, 'refunded'::text, 'cancelled'::text])", name='purchase_items_status_check'),
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], name='purchase_items_course_id_fkey'),
    ForeignKeyConstraint(['discount_id'], ['public.discounts.id'], name='purchase_items_discount_id_fkey'),
    ForeignKeyConstraint(['transaction_id'], ['public.transactions.id'], ondelete='CASCADE', name='purchase_items_transaction_id_fkey'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], name='purchase_items_user_id_fkey'),
        PrimaryKeyConstraint('id', name='purchase_items_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    transaction_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    original_price: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discounted_price: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'completed'::text"))
    discount_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    discount_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2))
    course_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    course: Mapped['Courses'] = relationship('Courses', back_populates='purchase_items')
    discount: Mapped[Optional['Discounts']] = relationship('Discounts', back_populates='purchase_items')
    transaction: Mapped['Transactions'] = relationship('Transactions', back_populates='purchase_items')
    user: Mapped['User'] = relationship('User', back_populates='purchase_items')
    discount_history: Mapped[list['DiscountHistory']] = relationship('DiscountHistory', back_populates='purchase_item')
    refund_requests: Mapped[list['RefundRequests']] = relationship('RefundRequests', back_populates='purchase_item')


class WithdrawalRequests(Base):
    __tablename__ = 'withdrawal_requests'
    __table_args__ = (
        CheckConstraint('amount > 0::numeric', name='withdrawal_requests_amount_check'),
        CheckConstraint("status::text = ANY (ARRAY['pending'::character varying::text, 'approved'::character varying::text, 'rejected'::character varying::text, 'payout_pending'::character varying::text, 'paid'::character varying::text, 'failed'::character varying::text, 'processing'::character varying::text])", name='withdrawal_requests_status_check'),
    ForeignKeyConstraint(['lecturer_id'], ['public.user.id'], name='withdrawal_requests_lecturer_id_fkey'),
    ForeignKeyConstraint(['transaction_id'], ['public.transactions.id'], name='withdrawal_requests_transactions_fk'),
        PrimaryKeyConstraint('id', name='withdrawal_requests_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    lecturer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'USD'::character varying"))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    paypal_batch_id: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    requested_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    approved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    rejected_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    reason: Mapped[Optional[str]] = mapped_column(Text)

    lecturer: Mapped['User'] = relationship('User', back_populates='withdrawal_requests')
    transaction: Mapped[Optional['Transactions']] = relationship('Transactions', back_populates='withdrawal_requests')


class DiscountHistory(Base):
    __tablename__ = 'discount_history'
    __table_args__ = (
    ForeignKeyConstraint(['discount_id'], ['public.discounts.id'], name='discount_history_discount_id_fkey'),
    ForeignKeyConstraint(['purchase_item_id'], ['public.purchase_items.id'], ondelete='CASCADE', name='discount_history_purchase_items_fk'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], name='discount_history_user_id_fkey'),
        PrimaryKeyConstraint('id', name='discount_history_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    purchase_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    discount_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    discounted_amount: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    discount: Mapped['Discounts'] = relationship('Discounts', back_populates='discount_history')
    purchase_item: Mapped['PurchaseItems'] = relationship('PurchaseItems', back_populates='discount_history')
    user: Mapped['User'] = relationship('User', back_populates='discount_history')


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
        Index('lesson_chunks_embedding_idx', 'embedding'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    lesson_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    chunk_index: Mapped[Optional[int]] = mapped_column(Integer)
    text_: Mapped[Optional[str]] = mapped_column('text', Text)
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(1536))
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    lesson: Mapped[Optional['Lessons']] = relationship('Lessons', back_populates='lesson_chunks')


class LessonCodes(Base):
    __tablename__ = 'lesson_codes'
    __table_args__ = (
        CheckConstraint("difficulty = ANY (ARRAY['easy'::text, 'medium'::text, 'hard'::text])", name='lesson_codes_difficulty_check'),
    ForeignKeyConstraint(['language_id'], ['public.supported_languages.id'], name='lesson_codes_language_id_fkey'),
    ForeignKeyConstraint(['lesson_id'], ['public.lessons.id'], ondelete='CASCADE', name='lesson_codes_lesson_id_fkey'),
        PrimaryKeyConstraint('id', name='lesson_codes_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    lesson_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    language_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    difficulty: Mapped[Optional[str]] = mapped_column(Text, server_default=text("'medium'::text"))
    time_limit: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('2'))
    memory_limit: Mapped[Optional[int]] = mapped_column(BigInteger, server_default=text('256000000'))
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('true'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    language: Mapped[Optional['SupportedLanguages']] = relationship('SupportedLanguages', back_populates='lesson_codes')
    lesson: Mapped['Lessons'] = relationship('Lessons', back_populates='lesson_codes')
    lesson_code_files: Mapped[list['LessonCodeFiles']] = relationship('LessonCodeFiles', back_populates='lesson_code')
    lesson_code_testcases: Mapped[list['LessonCodeTestcases']] = relationship('LessonCodeTestcases', back_populates='lesson_code')


class LessonComments(Base):
    __tablename__ = 'lesson_comments'
    __table_args__ = (
        CheckConstraint('depth >= 0', name='lesson_comments_depth_check'),
        CheckConstraint("status::text = ANY (ARRAY['visible'::character varying::text, 'hidden'::character varying::text, 'deleted'::character varying::text])", name='lesson_comments_status_check'),
    ForeignKeyConstraint(['lesson_id'], ['public.lessons.id'], ondelete='CASCADE', name='lesson_comments_lesson_id_fkey'),
    ForeignKeyConstraint(['parent_id'], ['public.lesson_comments.id'], ondelete='CASCADE', name='lesson_comments_parent_id_fkey'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='lesson_comments_user_id_fkey'),
        PrimaryKeyConstraint('id', name='lesson_comments_pkey'),
        Index('idx_lc_lesson_created', 'lesson_id', 'created_at'),
        Index('idx_lc_parent', 'parent_id'),
        Index('idx_lc_status', 'status'),
        Index('idx_lc_user', 'user_id'),
        Index('idx_lesson_comments_root_id', 'root_id'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    lesson_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    status: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'visible'::character varying"))
    depth: Mapped[Optional[int]] = mapped_column(SmallInteger, server_default=text('0'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    root_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    lesson: Mapped['Lessons'] = relationship('Lessons', back_populates='lesson_comments')
    parent: Mapped[Optional['LessonComments']] = relationship('LessonComments', remote_side=[id], back_populates='parent_reverse')
    parent_reverse: Mapped[list['LessonComments']] = relationship('LessonComments', remote_side=[parent_id], back_populates='parent')
    user: Mapped['User'] = relationship('User', back_populates='lesson_comments')
    lesson_comment_reactions: Mapped[list['LessonCommentReactions']] = relationship('LessonCommentReactions', back_populates='comment')


class LessonNotes(Base):
    __tablename__ = 'lesson_notes'
    __table_args__ = (
        CheckConstraint('time_seconds >= 0', name='lesson_notes_time_seconds_check'),
    ForeignKeyConstraint(['lesson_id'], ['public.lessons.id'], ondelete='CASCADE', name='lesson_notes_lesson_id_fkey'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='lesson_notes_user_id_fkey'),
        PrimaryKeyConstraint('id', name='lesson_notes_pkey'),
        Index('idx_lesson_notes_lesson_time', 'lesson_id', 'time_seconds'),
        Index('idx_lesson_notes_user', 'user_id'),
        Index('lesson_notes_embedding_idx', 'embedding'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    lesson_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(1536))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    lesson: Mapped['Lessons'] = relationship('Lessons', back_populates='lesson_notes')
    user: Mapped['User'] = relationship('User', back_populates='lesson_notes')


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
        Index('lesson_quizzes_embedding_idx', 'embedding'),
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
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(1536))
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
    embed_status: Mapped[Optional[str]] = mapped_column(Text, server_default=text("'idle'::text"))

    lesson: Mapped[Optional['Lessons']] = relationship('Lessons', back_populates='lesson_resources')
    resource_chunks: Mapped[list['ResourceChunks']] = relationship('ResourceChunks', back_populates='resource')


class LessonTutorMemory(Base):
    __tablename__ = 'lesson_tutor_memory'
    __table_args__ = (
    ForeignKeyConstraint(['lesson_id'], ['public.lessons.id'], ondelete='CASCADE', name='fk_ltm_lesson'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='fk_ltm_user'),
        PrimaryKeyConstraint('user_id', 'lesson_id', name='lesson_tutor_memory_pkey'),
        Index('idx_ltm_lesson', 'lesson_id'),
        Index('idx_ltm_user', 'user_id'),
        {'schema': 'public'}
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''::text"))
    key_topics: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    confusions: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    last_interaction_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))

    lesson: Mapped['Lessons'] = relationship('Lessons', back_populates='lesson_tutor_memory')
    user: Mapped['User'] = relationship('User', back_populates='lesson_tutor_memory')


class LessonVideos(Base):
    __tablename__ = 'lesson_videos'
    __table_args__ = (
    ForeignKeyConstraint(['lesson_id'], ['public.lessons.id'], ondelete='CASCADE', name='lesson_videos_lessons_fk'),
        PrimaryKeyConstraint('lesson_id', name='lesson_videos_pkey'),
        {'schema': 'public'}
    )

    lesson_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    video_url: Mapped[str] = mapped_column(Text, nullable=False)
    transcript: Mapped[Optional[str]] = mapped_column(Text)
    duration: Mapped[Optional[float]] = mapped_column(Double(53), server_default=text('0'))
    file_id: Mapped[Optional[str]] = mapped_column(String)
    source_type: Mapped[Optional[str]] = mapped_column(String, server_default=text("'upload_drive'::character varying"))
    # 🧩 Auto relationship (child → parent): Lessons
    lessons: Mapped['Lessons'] = relationship(
        'Lessons', back_populates='lesson_videos', uselist=False)


class RefundRequests(Base):
    __tablename__ = 'refund_requests'
    __table_args__ = (
        CheckConstraint("status::text = ANY (ARRAY['requested'::character varying::text, 'instructor_approved'::character varying::text, 'instructor_rejected'::character varying::text, 'admin_approved'::character varying::text, 'admin_rejected'::character varying::text, 'refunded'::character varying::text])", name='refund_requests_status_check'),
    ForeignKeyConstraint(['instructor_id'], ['public.user.id'], name='refund_requests_instructor_id_fkey'),
    ForeignKeyConstraint(['purchase_item_id'], ['public.purchase_items.id'], ondelete='CASCADE', name='refund_requests_purchase_item_id_fkey'),
    ForeignKeyConstraint(['resolved_by'], ['public.user.id'], name='refund_requests_resolved_by_fkey'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], name='refund_requests_user_id_fkey'),
        PrimaryKeyConstraint('id', name='refund_requests_pkey'),
        Index('idx_refund_requests_instructor', 'instructor_id'),
        Index('idx_refund_requests_purchase_item', 'purchase_item_id'),
        Index('idx_refund_requests_status', 'status'),
        Index('idx_refund_requests_user', 'user_id'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    purchase_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    instructor_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'requested'::character varying"))
    refund_amount: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    instructor_comment: Mapped[Optional[str]] = mapped_column(Text)
    admin_comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    instructor_reviewed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    admin_reviewed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    instructor: Mapped['User'] = relationship('User', foreign_keys=[instructor_id], back_populates='refund_requests')
    purchase_item: Mapped['PurchaseItems'] = relationship('PurchaseItems', back_populates='refund_requests')
    user: Mapped[Optional['User']] = relationship('User', foreign_keys=[resolved_by], back_populates='refund_requests_')
    user_: Mapped['User'] = relationship('User', foreign_keys=[user_id], back_populates='refund_requests1')


class TutorChatThreads(Base):
    __tablename__ = 'tutor_chat_threads'
    __table_args__ = (
        CheckConstraint("scope = ANY (ARRAY['lesson'::text, 'section'::text, 'course'::text])", name='ck_tutor_threads_scope'),
    ForeignKeyConstraint(['course_id'], ['public.courses.id'], ondelete='CASCADE', name='fk_tutor_threads_course'),
    ForeignKeyConstraint(['lesson_id'], ['public.lessons.id'], ondelete='CASCADE', name='fk_tutor_threads_lesson'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='fk_tutor_threads_user'),
        PrimaryKeyConstraint('id', name='tutor_chat_threads_pkey'),
        Index('idx_tutor_threads_active', 'user_id', 'lesson_id', 'scope'),
        Index('idx_tutor_threads_course', 'course_id', 'created_at'),
        Index('idx_tutor_threads_user_lesson_scope', 'user_id', 'lesson_id', 'scope', 'created_at'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    lesson_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'lesson'::text"))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    title: Mapped[Optional[str]] = mapped_column(Text)

    course: Mapped['Courses'] = relationship('Courses', back_populates='tutor_chat_threads')
    lesson: Mapped['Lessons'] = relationship('Lessons', back_populates='tutor_chat_threads')
    user: Mapped['User'] = relationship('User', back_populates='tutor_chat_threads')
    tutor_chat_messages: Mapped[list['TutorChatMessages']] = relationship('TutorChatMessages', back_populates='thread')


class LessonCodeFiles(Base):
    __tablename__ = 'lesson_code_files'
    __table_args__ = (
    ForeignKeyConstraint(['lesson_code_id'], ['public.lesson_codes.id'], ondelete='CASCADE', name='lesson_code_files_lesson_code_id_fkey'),
        PrimaryKeyConstraint('id', name='lesson_code_files_pkey'),
        UniqueConstraint('lesson_code_id', 'user_id', 'filename', 'role', name='lesson_code_files_lesson_code_id_user_id_filename_role_key'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    lesson_code_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Enum('solution', 'starter', 'user', name='code_file_role'), nullable=False, server_default=text("'solution'::code_file_role"), comment='Phân loại file: \n- solution = code chuẩn của giảng viên để verify\n- starter = code khung cho học viên ban đầu\n- user = code học viên đang sửa')
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    is_main: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    is_pass: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))

    lesson_code: Mapped['LessonCodes'] = relationship('LessonCodes', back_populates='lesson_code_files')


class LessonCodeTestcases(Base):
    __tablename__ = 'lesson_code_testcases'
    __table_args__ = (
    ForeignKeyConstraint(['lesson_code_id'], ['public.lesson_codes.id'], ondelete='CASCADE', name='lesson_code_testcases_lesson_code_id_fkey'),
        PrimaryKeyConstraint('id', name='lesson_code_testcases_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    lesson_code_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    input: Mapped[Optional[str]] = mapped_column(Text)
    expected_output: Mapped[Optional[str]] = mapped_column(Text)
    is_sample: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    order_index: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    lesson_code: Mapped['LessonCodes'] = relationship('LessonCodes', back_populates='lesson_code_testcases')


class LessonCommentReactions(Base):
    __tablename__ = 'lesson_comment_reactions'
    __table_args__ = (
    ForeignKeyConstraint(['comment_id'], ['public.lesson_comments.id'], ondelete='CASCADE', name='lesson_comment_reactions_comment_id_fkey'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='lesson_comment_reactions_user_id_fkey'),
        PrimaryKeyConstraint('id', name='lesson_comment_reactions_pkey'),
        UniqueConstraint('comment_id', 'user_id', name='lesson_comment_reactions_comment_id_user_id_key'),
        Index('idx_lcr_comment', 'comment_id'),
        Index('idx_lcr_user', 'user_id'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    comment_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    comment: Mapped['LessonComments'] = relationship('LessonComments', back_populates='lesson_comment_reactions')
    user: Mapped['User'] = relationship('User', back_populates='lesson_comment_reactions')


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


class ResourceChunks(Base):
    __tablename__ = 'resource_chunks'
    __table_args__ = (
    ForeignKeyConstraint(['lesson_id'], ['public.lessons.id'], ondelete='CASCADE', name='resource_chunks_lesson_id_fkey'),
    ForeignKeyConstraint(['resource_id'], ['public.lesson_resources.id'], ondelete='CASCADE', name='resource_chunks_resource_id_fkey'),
        PrimaryKeyConstraint('id', name='resource_chunks_pkey'),
        Index('idx_resource_chunks_embedding_hnsw', 'embedding'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('uuid_generate_v4()'))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    lesson_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    chunk_type: Mapped[Optional[str]] = mapped_column(Text, server_default=text("'pdf'::text"))
    embedding: Mapped[Optional[Any]] = mapped_column(VECTOR(1536))
    token_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    lesson: Mapped[Optional['Lessons']] = relationship('Lessons', back_populates='resource_chunks')
    resource: Mapped[Optional['LessonResources']] = relationship('LessonResources', back_populates='resource_chunks')


class TutorChatMessages(Base):
    __tablename__ = 'tutor_chat_messages'
    __table_args__ = (
        CheckConstraint("role = ANY (ARRAY['user'::text, 'assistant'::text, 'system'::text])", name='ck_tutor_messages_role'),
    ForeignKeyConstraint(['thread_id'], ['public.tutor_chat_threads.id'], ondelete='CASCADE', name='fk_tutor_messages_thread'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='fk_tutor_messages_user'),
        PrimaryKeyConstraint('id', name='tutor_chat_messages_pkey'),
        Index('idx_tutor_messages_thread_created', 'thread_id', 'created_at'),
        Index('idx_tutor_messages_user_created', 'user_id', 'created_at'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    thread_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))

    thread: Mapped['TutorChatThreads'] = relationship('TutorChatThreads', back_populates='tutor_chat_messages')
    user: Mapped['User'] = relationship('User', back_populates='tutor_chat_messages')
    tutor_chat_images: Mapped[list['TutorChatImages']] = relationship('TutorChatImages', back_populates='message')


class TutorChatImages(Base):
    __tablename__ = 'tutor_chat_images'
    __table_args__ = (
        CheckConstraint('file_size >= 0', name='ck_tutor_images_size'),
    ForeignKeyConstraint(['message_id'], ['public.tutor_chat_messages.id'], ondelete='CASCADE', name='fk_tutor_images_message'),
    ForeignKeyConstraint(['user_id'], ['public.user.id'], ondelete='CASCADE', name='fk_tutor_images_user'),
        PrimaryKeyConstraint('id', name='tutor_chat_images_pkey'),
        Index('idx_tutor_images_message', 'message_id'),
        Index('idx_tutor_images_user_created', 'user_id', 'created_at'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    message_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text('0'))
    ocr_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''::text"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    mime_type: Mapped[Optional[str]] = mapped_column(Text)

    message: Mapped['TutorChatMessages'] = relationship('TutorChatMessages', back_populates='tutor_chat_images')
    user: Mapped['User'] = relationship('User', back_populates='tutor_chat_images')


# === AUTO FIX SUMMARY ===
# • Đã đổi class kế thừa (trừ Base) → Base.
# • Đã thêm relationship() 1–1 hai chiều tự động (không trùng lặp).
# • Field dùng snake_case (vd: lesson_videos, course_reviews, ...).
# =========================
