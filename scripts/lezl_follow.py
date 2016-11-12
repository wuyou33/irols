#!/usr/bin/env python
import rospy
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, SetMode
from std_msgs.msg import Bool
from geometry_msgs.msg import PoseStamped, TwistStamped
from sensor_msgs.msg import Imu
from nav_msgs.msg import Odometry

class LEZL:
	def __init__(self):
		rospy.init_node('lezl')
		self.state_sub = rospy.Subscriber('/mavros/state',State,self.state_cb)
		self.odom_sub = rospy.Subscriber('/p3at/odom',Odometry,self.odom_cb)
		self.tracked_sub = rospy.Subscriber('/tracker/tracked',Bool,self.track_cb)
		self.heading_sub = rospy.Subscriber('/tracker/heading',TwistStamped,self.head_cb)
		local_pos_pub = rospy.Publisher('/mavros/setpoint_position/local',PoseStamped,queue_size=10)
		local_vel_pub = rospy.Publisher('/mavros/setpoint_velocity/cmd_vel',TwistStamped,queue_size=10)
		self.arming_client = rospy.ServiceProxy('/mavros/cmd/arming',CommandBool)
		self.set_mode_client = rospy.ServiceProxy('/mavros/set_mode',SetMode)
		self.state = State()
		self.tracked = False
		self.heading = TwistStamped()
		rate = rospy.Rate(20)
		while self.state.connected:
			rospy.spinOnce()
			rate.sleep()

		self.pose = PoseStamped()
		self.pose.pose.position.x = 0
		self.pose.pose.position.y = 0
		self.pose.pose.position.z = 10

		wait = rospy.Time.now()
		offb = True
		while not rospy.is_shutdown():
			if (self.state.mode != "OFFBOARD" and 
				(rospy.Time.now() - wait) > rospy.Duration(5)):
				print "Attempting to enter OFFBOARD"
				self.mode_switch("OFFBOARD")
				start = rospy.Time.now()
			else:
				if (not self.state.armed and
					(rospy.Time.now() - wait) > rospy.Duration(5)):
					print "Attempting to arm"
					self.arm_cmd(1)
				wait = rospy.Time.now()
			if not offb and self.state.mode == 'OFFBOARD':
				print "Watching for landing"
				self.watchdog(start)
			self.pose.header.stamp = rospy.Time.now()
			if not self.tracked:
				local_pos_pub.publish(self.pose)
			else:
				local_vel_pub.publish(self.heading)
			rate.sleep()
			
	def track_cb(self,data):
		self.tracked = data.data
	
	def head_cb(self,data):
		self.heading = data
		self.heading.twist.linear.x *= 0.125
		self.heading.twist.linear.y *= 0.125
		self.heading.twist.linear.z = 0

	def state_cb(self,data):
		self.state = data

	def odom_cb(self,data):
		x = data.pose.pose.position.x
		y = data.pose.pose.position.y
		self.pose.pose.position.x = -y
		self.pose.pose.position.y = x
		self.pose.pose.position.z = 5
		

	def watchdog(self,start):
		rate = rospy.Rate(1)
		while not rospy.is_shutdown():
			now = rospy.Time.now()
			if now-start > rospy.Duration(30):
				self.pose.pose.position.x = 2
				self.pose.pose.position.y = 2
				self.pose.pose.position.z = 0
				break
		self.land_time = rospy.Time.now()
		rospy.Subscriber('/mavros/imu/data',Imu,self.imu_cb)

	def imu_cb(self,data):
		threshold = 0.2
		while not rospy.is_shutdown():
			if (abs(data.linear_acceleration.z - 9.81) < threshold and
				(rospy.Time.now() - self.land_time) > rospy.Duration(5)):
				self.arm_cmd(0)			

	def arm_cmd(self,arming):
		if arming:
			self.arming_client(True)
		else:
			self.arming_client(False)

	def mode_switch(self,newmode):
		self.set_mode_client(custom_mode=newmode)

if __name__ == '__main__':
	lezl = LEZL()
