# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, redirect_with_hash
import logging
import qrcode
from io import BytesIO
import base64
import json
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class WeChatPay(http.Controller):

    def make_qrcode(self, qrurl):
        """根据URL生成二维码字符"""
        img = qrcode.make(qrurl)
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        heximage = base64.b64encode(buffer.getvalue())
        return "data:image/png;base64,{}".format(heximage.decode('utf-8'))

    @http.route('/shop/wechatpay', type='http', auth="public", website=True)
    def index(self, **kw):
        order = request.website.sale_get_order()
        # 获取微信支付
        acquirer = request.env['payment.acquirer'].sudo().search(
            [('provider', '=', 'wechatpay')], limit=1)
        res, data = acquirer._get_qrcode_url(order)
        values = {}
        if res:
            values['qrcode'] = self.make_qrcode(data)
            values['order'] = order.name
            values['amount'] = order.amount_total
        else:
            values['error'] = data
        return request.render("payment_wechatpay.wechatpay_pay", values)

    @http.route('/shop/wechatpay/result', type='http', auth="public", website=True)
    def wechatpay_query(self):
        """轮询支付结果"""
        order = request.website.sale_get_order()
        # 获取微信支付
        acquirer = request.env['payment.acquirer'].sudo().search(
            [('provider', '=', 'wechatpay')], limit=1)
        if acquirer.wechatpy_query_pay(order):
            # 支付成功
            return json.dumps({"result": 0, "order": order.name})
        return json.dumps({"result": 1, "order": order.name})

    def validate_pay_data(self, **kwargs):
        res = request.env['payment.transaction'].sudo(
        ).form_feedback(kwargs, 'wechatpay')
        return res

    @http.route('/payment/wechatpay/validate', type="http", auth="none", methods=['POST', 'GET'], csrf=False)
    def wechatpay_validate(self, **kwargs):
        """页面跳转后验证支付结果"""
        _logger.info("开始验证微信支付结果...")
        try:
            res = self.validate_pay_data(**kwargs)
        except ValidationError:
            _logger.exception("支付验证失败")
        return redirect_with_hash("/payment/process")

    @http.route('/payment/wechatpay/notify', csrf=False, type="http", auth='none', method=["POST"])
    def alipay_notify(self, **kwargs):
        """接收微信支付异步通知"""
        _logger.debug("接收微信支付异步通知...收到的数据:{}".format(request.httprequest.data))
        payment = request.env["payment.acquirer"].sudo().search(
            [('provider', '=', 'wechatpay')], limit=1)

        if payment._verify_wechatpay(request.httprequest.data):
            _logger.debug("回复微信")
            return b"""<xml><return_code><![CDATA[SUCCESS]]></return_code><return_msg><![CDATA[OK]]></return_msg></xml>"""
