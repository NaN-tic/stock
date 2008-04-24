from trytond.osv import fields, OSV


class Product(OSV):
    "Product"
    _name = "product.product"
    _inherit = "product.product"

    quantity = fields.Function('get_quantity', type='float', string='Quantity', fnct_search='search_quantity', readonly=True) #fct_inv ?


    def get_quantity(self, cursor, user, ids, name, args, context=None):
        if not (context and context.get('locations')):
            return dict([(id, False) for id in ids])
        location_ids = self.pool.get('stock.location').search(
            cursor, user, [('parent', 'child_of', context['locations'])],
            context=context)
        pbl = self.products_by_location(
            cursor, user, location_ids=location_ids, context=None)
        return dict([(line['product'], line['quantity']) for line in pbl])

    def _eval_domain(self, line, domain):
        res = True
        for field, operator, operand in domain:
            value = line.get(field)
            if not value:
                return False
            if operator not in ("=", ">=", "<=", ">", "<", "!="):
                return False
            if operator == "=":
                operator= "=="
            res = res and (eval(str(value) + operator + str(operand)))
        return res

    def search_quantity(self, cursor, user, name, domain=[], context=None):
        if not (context and context.get('locations')):
            return []
        location_ids = self.pool.get('stock.location').search(
            cursor, user, [('parent', 'child_of', context['locations'])],
            context=context)
        pbl = self.products_by_location(
            cursor, user, location_ids=location_ids, context=None)
        res= [line['product'] for line in pbl \
                    if self._eval_domain(line,domain)]
        return [('id', 'in', res)]


    def raw_products_by_location(self, cursor, user, location_ids,
                            product_ids=None, context=None):
        select_clause = \
            "select location, product, uom, sum(quantity) as quantity "\
             "from ( "\
               "SELECT to_location as location, product, uom, "\
                      "sum(quantity) as quantity "\
               "FROM stock_move "\
               "WHERE state = 'done' and to_%s "\
               "GROUP by to_location, product ,uom  "\
             "UNION  "\
               "SELECT from_location as location, product, uom, "\
                      "-sum(quantity) as quantity "\
               "FROM stock_move "\
               "WHERE state = 'done' and from_%s "\
               "GROUP by from_location, product, uom "\
             ") "\
            "as T group by T.location, T.product, T.uom "\

        where_clause = "location IN (" + \
            ",".join(["%s" for i in location_ids]) + ") "
        where_ids = location_ids
        if product_ids:
            where_clause += "AND product in (" + \
                ",".join(["%s" for i in product_ids]) + ")"
            where_ids += product_ids
        cursor.execute(select_clause % (where_clause, where_clause),
                       where_ids + where_ids)

        return cursor.fetchall()

    def products_by_location(self, cursor, user, location_ids,
                            product_ids=None, context=None):

        uom_obj = self.pool.get("product.uom")
        product_obj = self.pool.get("product.product")
        if not location_ids:
            return []
        if not product_ids:
            product_ids = product_obj.search(cursor, user, [], context=context)

        uom_ids = uom_obj.search(cursor, user, [], context=context)
        uom_by_id = dict((x.id, x) for x in uom_obj.browse(
                cursor, user, uom_ids, context=context))
        uom_by_prod = dict((x.id, x.default_uom) for x in product_obj.browse(
                cursor, user, product_ids, context=context))

        res = {}
        for line in self.raw_products_by_location(
            cursor, user, location_ids, product_ids, context=context):

            location, product, uom, quantity= line
            key = (location, product, uom)
            if key not in res:
                res[key] = 0
            res[key] += uom_obj.compute_qty(
                cursor, user, uom_by_id[uom], quantity, uom_by_prod[product])

        return [{'location': key[0],
                 'product':key[1],
                 'uom': key[2],
                 'quantity': val} for key,val in res.iteritems()]

Product()