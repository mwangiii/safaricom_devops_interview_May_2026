from app import db

class User(db.Model):
    __tablename__ = 'users'

    userid = db.Column(db.String, primary_key=True)
    firstname = db.Column(db.String)
    lastname = db.Column(db.String)
    email = db.Column(db.String, unique=True, nullable=False)
    password = db.Column(db.String, nullable=False)
    phone = db.Column(db.String)



class Organisation(db.Model):
    __tablename__ = 'organisations'
    orgid = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String)

class UserOrganisation(db.Model):
    __tablename__ = 'userorganisation'
    userid = db.Column(db.String, db.ForeignKey('users.userid'), primary_key=True)
    orgid = db.Column(db.String, db.ForeignKey('organisations.orgid'), primary_key=True)
