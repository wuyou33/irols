#!/usr/bin/env python
import rospy
import actionlib

import irols.msg
from irols.utils import euclidean_distance

from mavros_msgs.msg import State
from mavros_msgs.srv import SetMode
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry

class SeekServer(object):
    _feedback = irols.msg.DoSeekFeedback()
    _result = irols.msg.DoSeekResult()

    def __init__(self,name):
        self._action_name = name
        self._as = actionlib.SimpleActionServer(self._action_name,
                                                irols.msg.DoSeekAction,
                                                auto_start=False)
        self._as.register_goal_callback(self.goal_cb)
        self._as.register_preempt_callback(self.preempt_cb)

        rospy.wait_for_message('p3at/odom',Odometry)
        self.alt_sp = 10
        self.x_offset = 0
        self.y_offset = 0
        self.pos_sp = PoseStamped()
        self.odom_pub = rospy.Subscriber('p3at/odom',
                                         Odometry,
                                         self.handle_odom)
        self.curr_pos = rospy.wait_for_message('mavros/local_position/pose',
                                               PoseStamped).pose
        self.local_pos_sub = rospy.Subscriber('mavros/local_position/pose',
                                              PoseStamped,
                                              self.handle_local_pose)
        self.state = rospy.wait_for_message('mavros/state',State)
        self.state_sub = rospy.Subscriber('mavros/state',
                                          State,
                                          self.handle_state)
        self.pos_sp_pub = rospy.Publisher('mavros/setpoint_position/local',
                                             PoseStamped,
                                             queue_size=3)
        
        self.set_mode_client = rospy.ServiceProxy('mavros/set_mode',
                                                  SetMode)

        self._as.start()
        rospy.loginfo('{0}: online'.format(self._action_name))
#        self.execute_loop()
        


    def execute_loop(self):
        r = rospy.Rate(10)
        rospy.loginfo('{0}: euc_dist = {1}'.format(self._action_name,euclidean_distance(self.curr_pos,self.pos_sp)))
        while euclidean_distance(self.curr_pos,self.pos_sp) > 0.75:
            if self._as.is_preempt_requested():
                self._as.set_preempted(self._result)
                return
            if not self._as.is_active():
                rospy.loginfo('{0}: no goal active. Aborting.'.format(self._action_name))
                self._as.set_aborted()
                return
            if not self.state.mode == "OFFBOARD":
                rospy.loginfo('{0}: {1} --> {2}'.format(self._action_name,self.state.mode,'OFFBOARD'))
                self.set_mode_client(custom_mode="OFFBOARD")
            
            self.pos_sp.header.stamp = rospy.Time.now()
            self.pos_sp_pub.publish(self.pos_sp)
            self._feedback.distance = euclidean_distance(self.curr_pos,self.pos_sp)
            self._as.publish_feedback(self._feedback)
            r.sleep()
            if rospy.is_shutdown():
                if self._as.is_active():
                    self._as.set_aborted()
                return
        self._result.final_pos = self.curr_pos
        self._as.set_succeeded(self._result)
    
    def goal_cb(self):
        """implicitly sets any previous goal to preempted"""
        goal = self._as.accept_new_goal()
        self.alt_sp = goal.alt_sp
        self.x_offset = goal.x_offset
        self.y_offset = goal.y_offset
        rospy.loginfo('{0}: received goal: {1}'.format(self._action_name,goal))
        rospy.loginfo('{0}: current goal state is {1}'.format(self._action_name,self._as.is_active()))
        self.execute_loop()
    
    def preempt_cb(self):
        self._as.set_preempted(self._result)

    def handle_odom(self,data):
        x = data.pose.pose.position.x
        y = data.pose.pose.position.y
        self.pos_sp.pose.position.x = x + self.x_offset
        self.pos_sp.pose.position.y = y + self.y_offset
        self.pos_sp.pose.position.z = self.alt_sp
            

    def handle_local_pose(self,data):
        self.curr_pos = data.pose

    def handle_state(self,data):
        self.state = data

if __name__ == '__main__':
    rospy.init_node('seek_action_server')
    server = SeekServer('seek_action')
    rospy.spin()
