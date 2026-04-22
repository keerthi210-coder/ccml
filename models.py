from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# Many-to-many: Course ↔ Centre
course_centres = db.Table('course_centres',
    db.Column('course_id', db.Integer, db.ForeignKey('course.id'), primary_key=True),
    db.Column('centre_id', db.Integer, db.ForeignKey('centre.id'), primary_key=True)
)

class CourseCategory(db.Model):
    """Admin-managed course categories e.g. TNPSC, SSC, UPSC."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)   # stored UPPERCASE
    label = db.Column(db.String(120), default='')                  # display label
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256))
    google_id = db.Column(db.String(120), unique=True)
    avatar = db.Column(db.String(300), default='')
    mobile = db.Column(db.String(20), default='')
    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)       # OTP verified
    aadhaar_number = db.Column(db.String(14), default='')    # masked: XXXX-XXXX-1234
    aadhaar_doc = db.Column(db.String(300), default='')      # uploaded file path
    aadhaar_status = db.Column(db.String(20), default='none') # none/pending/approved/rejected
    aadhaar_remark = db.Column(db.String(200), default='')   # admin rejection reason
    present_address = db.Column(db.Text, default='')
    permanent_address = db.Column(db.Text, default='')
    blood_group = db.Column(db.String(10), default='')
    educational_qualification = db.Column(db.String(200), default='')
    dob = db.Column(db.String(20), default='')          # date of birth YYYY-MM-DD
    phone = db.Column(db.String(15), default='')        # verified phone number
    otp_code = db.Column(db.String(6), default='')
    otp_expires = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    enrollments = db.relationship('Enrollment', backref='user', lazy=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), default='')
    sub_category = db.Column(db.String(80), default='')
    mode = db.Column(db.String(40), default='Online')
    duration = db.Column(db.String(40), default='')
    lessons = db.Column(db.Integer, default=0)
    price = db.Column(db.Integer, default=0)
    original_price = db.Column(db.Integer, default=0)
    thumbnail = db.Column(db.String(300), default='')
    logo_url = db.Column(db.String(300), default='')   # exam logo
    youtube_url = db.Column(db.String(300), default='')   # YouTube embed URL
    badge = db.Column(db.String(60), default='')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    enrollments = db.relationship('Enrollment', backref='course', lazy=True)
    centres = db.relationship('Centre', secondary='course_centres', backref='courses', lazy=True)

    @property
    def price_inr(self):
        return self.price // 100

    @property
    def original_price_inr(self):
        return self.original_price // 100

    @property
    def discount_percent(self):
        if self.original_price > self.price > 0:
            return int((1 - self.price / self.original_price) * 100)
        return 0

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    payment_id = db.Column(db.String(120), default='')
    amount_paid = db.Column(db.Integer, default=0)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)

class Enquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(20), nullable=False)
    state = db.Column(db.String(80), default='')
    city = db.Column(db.String(80), default='')
    college = db.Column(db.String(120), default='')
    highest_degree = db.Column(db.String(80), default='')
    target_exam = db.Column(db.String(80), default='')
    preferred_course = db.Column(db.String(80), default='')
    message = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    duration_mins = db.Column(db.Integer, default=30)
    is_active = db.Column(db.Boolean, default=True)
    scheduled_date = db.Column(db.String(20), default='')   # YYYY-MM-DD
    scheduled_time = db.Column(db.String(10), default='10:00')  # HH:MM
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    course = db.relationship('Course', backref='tests')
    questions = db.relationship('Question', backref='test', lazy=True, cascade='all, delete-orphan')
    attempts = db.relationship('TestAttempt', backref='test', lazy=True, cascade='all, delete-orphan')
    registrations = db.relationship('TestRegistration', backref='test', lazy=True, cascade='all, delete-orphan')

    @property
    def is_global(self):
        return self.course_id is None

class TestRegistration(db.Model):
    """Non-user or user registration/interest for a scheduled test."""
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # null = non-user
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(15), default='')
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(300), nullable=False)
    option_b = db.Column(db.String(300), nullable=False)
    option_c = db.Column(db.String(300), nullable=False)
    option_d = db.Column(db.String(300), nullable=False)
    correct = db.Column(db.String(1), nullable=False)  # 'A','B','C','D'
    marks = db.Column(db.Integer, default=1)

class TestAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    total_marks = db.Column(db.Integer, default=0)
    correct_count = db.Column(db.Integer, default=0)
    wrong_count = db.Column(db.Integer, default=0)
    time_taken = db.Column(db.Integer, default=0)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    retake_after = db.Column(db.DateTime, nullable=True)  # 1 week lock
    user = db.relationship('User', backref='attempts')

class SummerCamp(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    start_date = db.Column(db.String(40), default='')
    end_date = db.Column(db.String(40), default='')
    age_group = db.Column(db.String(80), default='')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    gallery = db.relationship('CampGallery', backref='camp', lazy=True, cascade='all, delete-orphan')

class CampGallery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    camp_id = db.Column(db.Integer, db.ForeignKey('summer_camp.id'), nullable=False)
    image_url = db.Column(db.String(300), nullable=False)
    caption = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CampEnquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    camp_id = db.Column(db.Integer, db.ForeignKey('summer_camp.id'), nullable=True)
    child_name = db.Column(db.String(120), nullable=False)
    parent_name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), default='')
    age = db.Column(db.String(10), default='')
    activity = db.Column(db.String(80), default='')
    message = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    camp = db.relationship('SummerCamp', backref='enquiries')

class CampActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(10), default='🎯')
    tagline = db.Column(db.String(200), default='')
    description = db.Column(db.Text, default='')
    age_group = db.Column(db.String(80), default='6–16 years')
    duration = db.Column(db.String(80), default='')
    benefits = db.Column(db.Text, default='')   # newline-separated
    image_url = db.Column(db.String(300), default='')
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

class HeroBanner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(300), nullable=False)
    title = db.Column(db.String(200), default='')
    subtitle = db.Column(db.String(300), default='')
    badge = db.Column(db.String(100), default='')
    btn_text = db.Column(db.String(80), default='Explore Courses')
    btn_link = db.Column(db.String(200), default='#')
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

class ActivityPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('camp_activity.id'), nullable=False)
    image_url = db.Column(db.String(300), nullable=False)
    caption = db.Column(db.String(200), default='')
    order = db.Column(db.Integer, default=0)
    activity = db.relationship('CampActivity', backref='photos')

class SiteSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, default='')
    label = db.Column(db.String(200), default='')
    setting_type = db.Column(db.String(20), default='text')  # text, textarea, image

class CourseVideo(db.Model):
    """Recorded online class videos uploaded by admin for a course."""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    video_url = db.Column(db.String(300), nullable=False)  # YouTube embed or direct URL
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    course = db.relationship('Course', backref='videos')

class CourseMaterial(db.Model):
    """PDF / study material uploaded by admin for a course."""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    file_url = db.Column(db.String(300), nullable=False)   # path or Cloudinary URL
    file_type = db.Column(db.String(10), default='pdf')    # pdf, doc, etc.
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    course = db.relationship('Course', backref='materials')

class Centre(db.Model):
    """Learning centres — KSC, Padaipagam I, Padaipagam II."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)  # ksc, padaipagam-1, padaipagam-2
    description = db.Column(db.Text, default='')
    address = db.Column(db.String(300), default='')
    image_url = db.Column(db.String(300), default='')
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    coming_soon = db.Column(db.Boolean, default=False)

class Testimonial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(120), default='')
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)
    avatar_letter = db.Column(db.String(5), default='')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class GalleryPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(300), nullable=False)
    caption = db.Column(db.String(200), default='')
    category = db.Column(db.String(80), default='')  # ksc, padaipagam, summer-camp, general
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
